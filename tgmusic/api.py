from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qsl

from aiogram import Bot
from aiohttp import web

from .db import DB, Track

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Telegram Mini App initData validation
# https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
# ---------------------------------------------------------------------------

INIT_DATA_MAX_AGE = 24 * 3600  # seconds


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
    # max_age check: caller can pass 0 to disable.
    import time
    if max_age and (time.time() - auth_date) > max_age:
        raise ValueError("init_data expired")

    if "user" in data:
        data["user"] = json.loads(data["user"])
    return data


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

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
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Vary"] = "Origin"
    return resp


@web.middleware
async def auth_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.StreamResponse:
    # OPTIONS preflight and /health bypass auth.
    if request.method == "OPTIONS" or request.path in ("/health",):
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


async def play(request: web.Request) -> web.Response:
    """Send a track back to the owner's chat with the bot so the native
    Telegram player picks it up with background/lockscreen support.
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
    user_id = request["user_id"]
    await bot.send_audio(chat_id=user_id, audio=track.file_id)
    return web.json_response({"ok": True, "track_id": track_id})


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def build_app(*, bot: Bot, db: DB, bot_token: str, owner_id: int, cors_origin: str) -> web.Application:
    app = web.Application(
        middlewares=[cors_middleware, auth_middleware],
    )
    app["bot"] = bot
    app["db"] = db
    app["bot_token"] = bot_token
    app["owner_id"] = owner_id
    app["cors_origin"] = cors_origin

    app.router.add_get("/health", health)
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/tracks/recent", tracks_recent)
    app.router.add_get("/api/tracks/search", tracks_search)
    app.router.add_get("/api/artists", artists)
    app.router.add_post("/api/play", play)
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
