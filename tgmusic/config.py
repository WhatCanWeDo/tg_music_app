from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    owner_id: int
    db_path: Path
    web_host: str
    web_port: int
    cors_origin: str  # exact origin or "*"
    public_base_url: str  # used to build signed stream URLs; empty = derive from request


def load(env_file: str | Path = ".env") -> Config:
    load_dotenv(env_file, override=False)

    bot_token = os.environ.get("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError(
            "BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )

    raw_owner = os.environ.get("OWNER_ID", "").strip()
    if not raw_owner:
        raise RuntimeError(
            "OWNER_ID is not set. Ask @userinfobot for your Telegram numeric ID."
        )
    try:
        owner_id = int(raw_owner)
    except ValueError as e:
        raise RuntimeError(f"OWNER_ID must be a number, got: {raw_owner!r}") from e

    db_path = Path(os.environ.get("DB_PATH", "tgmusic.db")).expanduser().resolve()
    web_host = os.environ.get("WEB_HOST", "127.0.0.1").strip()
    web_port = int(os.environ.get("WEB_PORT", "8080"))
    cors_origin = os.environ.get("CORS_ORIGIN", "*").strip()
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "").strip()

    return Config(
        bot_token=bot_token,
        owner_id=owner_id,
        db_path=db_path,
        web_host=web_host,
        web_port=web_port,
        cors_origin=cors_origin,
        public_base_url=public_base_url,
    )
