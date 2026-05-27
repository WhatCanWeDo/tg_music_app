from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qsl, quote

import aiohttp
from aiogram import Bot
from aiohttp import web

from .db import DB, Track

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Telegram Mini App initData validation
# https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
# ---------------------------------------------------------------------------

INIT_DATA_MAX_AGE = 24 * 3600  # seconds
STREAM_URL_TTL = 12 * 3600  # seconds — how long a signed stream URL is valid


def validate_init_data(
    init_data: str, bot_token: str, max_age: int = INIT_DATA_MAX_AGE
) -> dict[str, Any]:
    """Verify HMAC of Telegram initData. Returns parsed payload or raises."""
    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise ValueError("missing hash")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items())
    )
    secret_key = hmac.new(
        key=b"WebAppData", msg=bot_token.encode(), digestmod=hashlib.sha256
    ).digest()
    expected_hash = hmac.new(
        key=secret_key, msg=data_check_string.encode(), digestmod=hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("invalid hash")

    auth_date = int(data.get("auth_date", "0"))
    if auth_date == 0:
        raise ValueError("missing auth_date")
    if max_age and (time.time() - auth_date) > max_age:
        raise ValueError("init_data expired")

    if "user" in data:
        data["user"] = json.loads(data["user"])
    return data


# ---------------------------------------------------------------------------
# Signed-URL scheme for /api/stream — keeps audio URLs usable in <audio> tags
# (which can't send Authorization headers) while preventing arbitrary access.
# ---------------------------------------------------------------------------

def _sign_stream(track_id: int, exp: int, bot_token: str) -> str:
    message = f"{track_id}:{exp}".encode()
    return hmac.new(bot_token.encode(), message, hashlib.sha256).hexdigest()[:32]


def make_stream_url(base: str, track_id: int, bot_token: str, ttl: int = STREAM_URL_TTL) -> str:
    exp = int(time.time()) + ttl
    sig = _sign_stream(track_id, exp, bot_token)
    return f"{base}/api/stream/{track_id}?exp={exp}&sig={sig}"


def _verify_stream_sig(track_id: int, exp: int, sig: str, bot_token: str) -> bool:
    expected = _sign_stream(track_id, exp, bot_token)
    return hmac.compare_digest(expected, sig)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

PUBLIC_PREFIXES = ("/health", "/api/stream/")  # auth handled per-route


@web.middleware
async def cors_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.StreamResponse:
    origin = request.app["cors_origin"]
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Range"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range, Accept-Ranges"
    resp.headers["Vary"] = "Origin"
    return resp


@web.middleware
async def auth_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.StreamResponse:
    if request.method == "OPTIONS" or any(
        request.path.startswith(p) for p in PUBLIC_PREFIXES
    ):
        return await handler(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("tma "):
        raise web.HTTPUnauthorized(text="missing tma init_data")
    init_data = auth[4:]
    try:
        payload = validate_init_data(init_data, request.app["bot_token"])
    except ValueError as e:
        log.warning("init_data rejected: %s", e)
        raise web.HTTPUnauthorized(text=f"bad init_data: {e}") from e

    user = payload.get("user") or {}
    user_id = int(user.get("id", 0))
    if user_id != request.app["owner_id"]:
        log.warning(
            "rejecting user_id=%s (not owner=%s)", user_id, request.app["owner_id"]
        )
        raise web.HTTPForbidden(text="not the owner")

    request["user_id"] = user_id
    return await handler(request)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def health(_: web.Request) -> web.Response:
    return web.Response(text="ok")


async def me(request: web.Request) -> web.Response:
    db: DB = request.app["db"]
    counts = await db.counts()
    return web.json_response({
        "user_id": request["user_id"],
        "counts": counts,
    })


async def tracks_recent(request: web.Request) -> web.Response:
    db: DB = request.app["db"]
    limit = _clamp_int(request.query.get("limit"), default=20, lo=1, hi=200)
    tracks = await db.recent(limit=limit)
    return web.json_response([_track_to_dict(t) for t in tracks])


async def tracks_search(request: web.Request) -> web.Response:
    db: DB = request.app["db"]
    query = (request.query.get("q") or "").strip()
    if not query:
        return web.json_response([])
    limit = _clamp_int(request.query.get("limit"), default=30, lo=1, hi=200)
    tracks = await db.search(query, limit=limit)
    return web.json_response([_track_to_dict(t) for t in tracks])


async def artists(request: web.Request) -> web.Response:
    db: DB = request.app["db"]
    limit = _clamp_int(request.query.get("limit"), default=100, lo=1, hi=500)
    rows = await db.top_artists(limit=limit)
    return web.json_response([{"name": n, "track_count": c} for n, c in rows])


async def play_url(request: web.Request) -> web.Response:
    """Return a signed stream URL the Mini App can plug straight into <audio>."""
    db: DB = request.app["db"]
    body = await request.json()
    track_id = int(body.get("track_id", 0))
    if track_id <= 0:
        raise web.HTTPBadRequest(text="track_id required")
    track = await db.get(track_id)
    if track is None:
        raise web.HTTPNotFound(text=f"no track {track_id}")

    base = request.app["public_base_url"] or _derive_base(request)
    url = make_stream_url(base, track.id, request.app["bot_token"])
    return web.json_response({"url": url, "track_id": track.id})


async def play_to_chat(request: web.Request) -> web.Response:
    """Fallback: send the track to the owner's chat so the native Telegram
    player can play it in the background (lockscreen, AirPods, car BT).
    """
    db: DB = request.app["db"]
    bot: Bot = request.app["bot"]
    body = await request.json()
    track_id = int(body.get("track_id", 0))
    if track_id <= 0:
        raise web.HTTPBadRequest(text="track_id required")
    track = await db.get(track_id)
    if track is None:
        raise web.HTTPNotFound(text=f"no track {track_id}")
    await bot.send_audio(chat_id=request["user_id"], audio=track.file_id)
    return web.json_response({"ok": True, "track_id": track_id})


async def stream(request: web.Request) -> web.StreamResponse:
    """Stream the underlying Telegram CDN audio file to the client.

    Authenticated by signed query string (HMAC-SHA256 of track_id+exp keyed by
    bot_token). <audio> tags can't send custom headers, so this bypasses the
    initData auth middleware and uses a self-contained signature instead.
    """
    track_id = int(request.match_info["track_id"])
    sig = request.query.get("sig", "")
    try:
        exp = int(request.query.get("exp", "0"))
    except ValueError:
        raise web.HTTPForbidden(text="bad exp")
    bot_token: str = request.app["bot_token"]
    if not _verify_stream_sig(track_id, exp, sig, bot_token):
        raise web.HTTPForbidden(text="bad signature")
    if exp < int(time.time()):
        raise web.HTTPGone(text="url expired — refresh the page")

    db: DB = request.app["db"]
    track = await db.get(track_id)
    if track is None:
        raise web.HTTPNotFound()

    bot: Bot = request.app["bot"]
    tg_file = await bot.get_file(track.file_id)
    file_path = tg_file.file_path
    if not file_path:
        raise web.HTTPServiceUnavailable(text="Telegram returned no file_path")
    file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

    session: aiohttp.ClientSession = request.app["http_session"]
    upstream_headers: dict[str, str] = {}
    if (rng := request.headers.get("Range")):
        upstream_headers["Range"] = rng

    upstream = await session.get(file_url, headers=upstream_headers)
    try:
        if upstream.status >= 400:
            text = await upstream.text()
            log.warning("upstream %s for track %s: %s", upstream.status, track_id, text[:200])
            raise web.HTTPBadGateway(text=f"Telegram CDN: {upstream.status}")

        response = web.StreamResponse(status=upstream.status)
        response.headers["Content-Type"] = track.mime_type or "audio/mpeg"
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Cache-Control"] = "private, max-age=3600"
        # Inline disposition with a sensible filename for "save as".
        fname = track.file_name or f"track-{track.id}.mp3"
        response.headers["Content-Disposition"] = (
            f'inline; filename="{quote(fname.encode("ascii", "ignore").decode() or f"track-{track.id}.mp3")}"'
        )
        for h in ("Content-Length", "Content-Range"):
            if h in upstream.headers:
                response.headers[h] = upstream.headers[h]

        await response.prepare(request)
        async for chunk in upstream.content.iter_chunked(64 * 1024):
            await response.write(chunk)
        await response.write_eof()
        return response
    finally:
        upstream.release()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def build_app(
    *,
    bot: Bot,
    db: DB,
    bot_token: str,
    owner_id: int,
    cors_origin: str,
    public_base_url: str = "",
) -> web.Application:
    app = web.Application(
        middlewares=[cors_middleware, auth_middleware],
        client_max_size=1024 * 1024,  # we don't take uploads; small POST bodies only
    )
    app["bot"] = bot
    app["db"] = db
    app["bot_token"] = bot_token
    app["owner_id"] = owner_id
    app["cors_origin"] = cors_origin
    app["public_base_url"] = public_base_url.rstrip("/")

    async def on_startup(app: web.Application) -> None:
        app["http_session"] = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_read=60),
        )

    async def on_cleanup(app: web.Application) -> None:
        session: aiohttp.ClientSession | None = app.get("http_session")
        if session is not None:
            await session.close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_get("/health", health)
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/tracks/recent", tracks_recent)
    app.router.add_get("/api/tracks/search", tracks_search)
    app.router.add_get("/api/artists", artists)
    app.router.add_post("/api/play/url", play_url)
    app.router.add_post("/api/play/to-chat", play_to_chat)
    app.router.add_get("/api/stream/{track_id}", stream)
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _track_to_dict(t: Track) -> dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "artist": t.artist,
        "album": t.album,
        "duration_s": t.duration_s,
        "file_name": t.file_name,
        "thumb_file_id": t.thumb_file_id,
    }


def _clamp_int(raw: str | None, *, default: int, lo: int, hi: int) -> int:
    if raw is None:
        return default
    try:
        n = int(raw)
    except ValueError:
        return default
    return max(lo, min(hi, n))


def _derive_base(request: web.Request) -> str:
    """Reconstruct the public base URL from request headers (cloudflared
    forwards X-Forwarded-Proto/Host)."""
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host") or ""
    return f"{proto}://{host}"
