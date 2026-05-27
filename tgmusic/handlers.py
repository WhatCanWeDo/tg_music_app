from __future__ import annotations

import html
import logging
from typing import cast

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Audio, Message

from .db import DB, Track

log = logging.getLogger(__name__)


def build_router(db: DB, owner_id: int) -> Router:
    """Build a Router whose handlers are gated to OWNER_ID.

    If owner_id == 0, the router runs in discovery mode: it replies to any
    sender with their Telegram ID. Used once on first deploy to bootstrap.
    """
    router = Router(name="tgmusic")

    if owner_id == 0:
        @router.message()
        async def discovery(message: Message) -> None:
            uid = message.from_user.id if message.from_user else None
            log.warning("DISCOVERY: incoming message from user_id=%s", uid)
            await message.answer(
                f"👋 Discovery mode.\n\n"
                f"Your Telegram ID: <code>{uid}</code>\n\n"
                f"Set <code>OWNER_ID={uid}</code> in <code>.env</code> on the "
                f"server and restart the bot.",
                parse_mode="HTML",
            )
        return router

    router.message.filter(F.from_user.id == owner_id)

    @router.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        c = await db.counts()
        await message.answer(
            "👋 <b>tgmusic</b> — твоя личная библиотека.\n\n"
            f"Сейчас в базе: <b>{c['tracks']}</b> треков, "
            f"<b>{c['artists']}</b> артистов, "
            f"<b>{_fmt_duration(c['total_seconds'])}</b> музыки.\n\n"
            "<b>Что делать дальше:</b>\n"
            "• Пересылай боту любые audio-треки — они проиндексируются\n"
            "• /list — последние добавленные\n"
            "• /search &lt;запрос&gt; — поиск\n"
            "• /artists — топ артистов\n"
            "• /play &lt;id&gt; — проиграть конкретный трек\n"
            "• /stats — статистика библиотеки",
            parse_mode="HTML",
        )

    @router.message(Command("stats"))
    async def cmd_stats(message: Message) -> None:
        c = await db.counts()
        await message.answer(
            f"📊 <b>Статистика</b>\n"
            f"Треки: <b>{c['tracks']}</b>\n"
            f"Артисты: <b>{c['artists']}</b>\n"
            f"Альбомы: <b>{c['albums']}</b>\n"
            f"Общая длительность: <b>{_fmt_duration(c['total_seconds'])}</b>",
            parse_mode="HTML",
        )

    @router.message(Command("list"))
    async def cmd_list(message: Message, command: CommandObject) -> None:
        limit = _parse_int_arg(command.args, default=10, min_val=1, max_val=100)
        tracks = await db.recent(limit=limit)
        await message.answer(_format_track_list(tracks, header="🆕 Последние"), parse_mode="HTML")

    @router.message(Command("search"))
    async def cmd_search(message: Message, command: CommandObject) -> None:
        query = (command.args or "").strip()
        if not query:
            await message.answer("Использование: <code>/search queen</code>", parse_mode="HTML")
            return
        tracks = await db.search(query, limit=30)
        if not tracks:
            await message.answer(f"Ничего не нашлось по запросу <i>{html.escape(query)}</i>.", parse_mode="HTML")
            return
        await message.answer(
            _format_track_list(tracks, header=f"🔎 Найдено по «{html.escape(query)}»"),
            parse_mode="HTML",
        )

    @router.message(Command("artists"))
    async def cmd_artists(message: Message) -> None:
        rows = await db.top_artists(limit=30)
        if not rows:
            await message.answer("Артистов пока нет — пришли треки.")
            return
        lines = ["🎤 <b>Топ артистов</b>", ""]
        for artist, n in rows:
            lines.append(f"• <b>{html.escape(artist)}</b> — {n}")
        await message.answer("\n".join(lines), parse_mode="HTML")

    @router.message(Command("play"))
    async def cmd_play(message: Message, command: CommandObject) -> None:
        track_id = _parse_int_arg(command.args, default=None, min_val=1)
        if track_id is None:
            await message.answer("Использование: <code>/play 42</code>", parse_mode="HTML")
            return
        track = await db.get(track_id)
        if track is None:
            await message.answer(f"Трека с id={track_id} нет.")
            return
        await message.answer_audio(
            audio=track.file_id,
            caption=f"<i>{html.escape(track.display)}</i>",
            parse_mode="HTML",
        )

    @router.message(F.audio)
    async def ingest_audio(message: Message) -> None:
        audio = cast(Audio, message.audio)
        thumb_file_id = audio.thumbnail.file_id if audio.thumbnail else None
        track_id, was_new = await db.upsert_track(
            file_id=audio.file_id,
            file_unique_id=audio.file_unique_id,
            title=audio.title,
            artist=audio.performer,
            album=None,  # Telegram Audio doesn't expose album; mutagen later.
            duration_s=audio.duration,
            file_name=audio.file_name,
            mime_type=audio.mime_type,
            file_size=audio.file_size,
            thumb_file_id=thumb_file_id,
            source_chat_id=message.chat.id,
            source_message_id=message.message_id,
        )
        verb = "📥 Добавлен" if was_new else "♻️ Уже в библиотеке"
        title = audio.title or audio.file_name or "Untitled"
        artist = audio.performer or "Unknown Artist"
        await message.reply(
            f"{verb} <code>id={track_id}</code>\n"
            f"<b>{html.escape(artist)}</b> — {html.escape(title)}",
            parse_mode="HTML",
        )

    @router.message(F.text)
    async def fallback_text(message: Message) -> None:
        # Anything else just nudges the user toward commands.
        await message.answer(
            "Не понял. Пришли audio-трек или используй команды: "
            "/list, /search, /artists, /stats."
        )

    return router


def _parse_int_arg(
    raw: str | None,
    *,
    default: int | None,
    min_val: int = 1,
    max_val: int | None = None,
) -> int | None:
    if not raw:
        return default
    try:
        n = int(raw.strip().split()[0])
    except (ValueError, IndexError):
        return default
    if n < min_val:
        return min_val
    if max_val is not None and n > max_val:
        return max_val
    return n


def _format_track_list(tracks: list[Track], header: str) -> str:
    if not tracks:
        return f"{header}: пусто. Пришли треки боту."
    lines = [f"<b>{header}</b>", ""]
    for t in tracks:
        lines.append(
            f"<code>{t.id:>4}</code>  {html.escape(t.display)}"
        )
    lines.append("")
    lines.append("Чтобы проиграть: <code>/play &lt;id&gt;</code>")
    return "\n".join(lines)


def _fmt_duration(total_seconds: int) -> str:
    hours, rem = divmod(total_seconds, 3600)
    minutes, _ = divmod(rem, 60)
    if hours:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"
