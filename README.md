# tgmusic

Личная музыкальная библиотека поверх Telegram. Бот принимает форварды
аудио, индексирует в SQLite, отдаёт обратно через нативный плеер Telegram
(работает в фоне, на lockscreen, через AirPods).

См. полный design doc: `~/.gstack/projects/tg_music_app/`.

## MVP scope (этот шаг)

- [x] Бот принимает пересланные / отправленные audio-сообщения
- [x] Извлекает метаданные из Telegram Audio (title, performer, duration, thumb)
- [x] Сохраняет в SQLite (`file_id`, `file_unique_id`, теги)
- [x] Команды: `/start`, `/stats`, `/list`, `/search`, `/play`, `/artists`
- [x] Whitelist на твой `OWNER_ID` — никто другой не может пользоваться ботом

Следующее (отдельно): Mini App на React, обогащение метаданных через mutagen,
плейлисты, обложки из MusicBrainz.

## Setup

1. **Создай бота через @BotFather:**
   - `/newbot`
   - Имя — любое (например `<твоё-имя> Music`)
   - Username — например `mshekhunov_music_bot`
   - Скопируй токен

2. **Узнай свой Telegram ID:**
   - Напиши [@userinfobot](https://t.me/userinfobot) → пришлёт `Id: 123456789`

3. **Установи зависимости:**
   ```bash
   cd ~/tg_music_app
   uv sync
   ```

4. **Заполни `.env`:**
   ```bash
   cp .env.example .env
   # Открой .env и впиши BOT_TOKEN и OWNER_ID
   ```

5. **Запусти:**
   ```bash
   uv run python -m tgmusic
   ```

## Использование

В Telegram найди своего бота, нажми `/start`. Затем:

- **Перешли любой audio-трек боту** — он проиндексирует и подтвердит сохранение.
- `/stats` — сколько треков, артистов в библиотеке.
- `/list` — последние 10 треков.
- `/list 30` — последние 30.
- `/search queen` — поиск по `title`, `artist`, `file_name`.
- `/artists` — топ-30 артистов с количеством треков.
- `/play 42` — отправит трек с `id=42` обратно в чат → нажми play в нативном плеере.

## Архитектура

```
tgmusic/
├── __main__.py    # python -m tgmusic — entry point, polling loop
├── config.py      # загрузка .env
├── db.py          # SQLite schema + async queries (aiosqlite)
└── handlers.py    # aiogram handlers (ingest + commands)
```

База: `tgmusic.db` в корне (SQLite, configurable через `DB_PATH`).

## Чего ещё нет

Список того, что отложено до следующих шагов:

- **Mini App** — React-фронт в стиле Spotify. Будет дёргать REST API бэка
  и вызывать `/play` под капотом.
- **Album / year / track number** — Telegram Audio даёт только title и
  performer. Album extraction через mutagen — следующая итерация.
- **Cover art** — есть `thumb_file_id`, но фронт пока его не показывает.
- **Userbot bootstrap** — Telethon-скрипт, который засосёт всё из Saved
  Messages одним прогоном. Deferred до момента, когда ручной форвардинг
  станет болезненным.
- **Дедупликация по acoustic fingerprint** (Chromaprint) — позже.

## Хостинг

- **Локально:** просто `uv run python -m tgmusic` в `tmux` / `screen`.
- **На сервере / Mac mini 24/7:** см. секцию "Distribution Plan" в design doc.
  Простейший вариант — `systemd --user` сервис или `launchd` plist на Mac.
