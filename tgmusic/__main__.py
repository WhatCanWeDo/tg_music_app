from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

from . import config
from .api import build_app
from .db import DB
from .handlers import build_router


async def amain() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("tgmusic")

    cfg = config.load()
    log.info("DB: %s", cfg.db_path)
    if cfg.owner_id == 0:
        log.warning(
            "OWNER_ID=0 — running in DISCOVERY MODE. Send any message to the "
            "bot to learn your Telegram ID, then set OWNER_ID and restart."
        )
    else:
        log.info("Owner: %s", cfg.owner_id)

    db = DB(cfg.db_path)
    await db.init()

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()
    dp.include_router(build_router(db, cfg.owner_id))

    me = await bot.get_me()
    log.info("Started as @%s", me.username)

    # Build web app for the Mini App backend
    api_app = build_app(
        bot=bot,
        db=db,
        bot_token=cfg.bot_token,
        owner_id=cfg.owner_id,
        cors_origin=cfg.cors_origin,
    )
    runner = web.AppRunner(api_app)
    await runner.setup()
    site = web.TCPSite(runner, cfg.web_host, cfg.web_port)
    await site.start()
    log.info("HTTP API listening on http://%s:%s", cfg.web_host, cfg.web_port)

    try:
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        await runner.cleanup()
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(amain())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
