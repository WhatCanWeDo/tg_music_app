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

## Mini App

В `webapp/` лежит React-фронт. Он рендерит библиотеку, поиск и список артистов,
а на тап трека POST-ит в `/api/play` — бэк шлёт audio через `sendAudio` в твой
чат с ботом, и нативный плеер Telegram играет с фоном/lockscreen.

### Backend HTTP API (живёт внутри того же python-процесса)

| Method | Path                          | Auth | Что делает                                                  |
|--------|-------------------------------|------|-------------------------------------------------------------|
| GET    | `/health`                     | —    | sanity check                                                |
| GET    | `/api/me`                     | tma  | счётчики библиотеки                                         |
| GET    | `/api/tracks/recent`          | tma  | последние треки (`?limit=20`)                               |
| GET    | `/api/tracks/search`          | tma  | поиск (`?q=...&limit=30`)                                   |
| GET    | `/api/artists`                | tma  | топ артистов (`?limit=100`)                                 |
| POST   | `/api/play/url`               | tma  | `{track_id}` → `{url}` — подписанный URL для `<audio src>`  |
| POST   | `/api/play/to-chat`           | tma  | `{track_id}` → sendAudio в чат (для фона через native player) |
| GET    | `/api/stream/{id}?exp&sig`    | sig  | стрим аудио с Telegram CDN, поддержка Range                 |

`tma` = заголовок `Authorization: tma <initData>` (Telegram WebApp подписанные данные). Бэк проверяет HMAC и сверяет `user.id` с `OWNER_ID`.

`sig` = подпись в query-параметрах (`exp` — unix timestamp, `sig` — HMAC-SHA256 от `track_id+exp` ключом `BOT_TOKEN`). Нужно потому что `<audio>` тег не умеет слать кастомные заголовки.

**UX-модель:**
- Тап на треке в Mini App → in-app плеер начинает играть (стрим через `<audio>`).
- Кнопка ⤴ справа от трека → отправляет в чат для нативного плеера Telegram (фон, lockscreen, AirPods).
- iOS Safari WebView вешает HTML5-аудио при потере фокуса, поэтому in-app плеер — для активного слушания, а ⤴ — для "положил в карман, побежал".

### Деплой Mini App на Cloudflare Pages

1. **Cloudflare аккаунт** (бесплатный) — https://dash.cloudflare.com
2. **Workers & Pages** → Create → Pages → "Connect to Git" → выбери репо
   `tg_music_app`
3. **Build settings:**
   - Framework preset: `Vite`
   - Build command: `bun install && bun run build` (или `npm install && npm run build`)
   - Build output directory: `webapp/dist`
   - Root directory: `webapp`
4. **Environment variables (Production):**
   - `VITE_API_URL` = текущий URL cloudflared-туннеля (см. ниже как узнать)
5. **Save & deploy.** Через минуту получишь URL вида
   `tg-music-app.pages.dev`.

После деплоя обнови **CORS_ORIGIN** на VPS на этот URL:
```bash
ssh personal-vps
sed -i 's|^CORS_ORIGIN=.*|CORS_ORIGIN=https://tg-music-app.pages.dev|' /root/tg_music_app/.env
systemctl restart tgmusic
```

### Узнать текущий URL туннеля

URL `*.trycloudflare.com` пересоздаётся при каждом рестарте cloudflared
(обычно после reboot VPS). Чтобы увидеть текущий:
```bash
ssh personal-vps 'journalctl -u cloudflared-tgmusic -o cat | \
  grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" | head -1'
```

Если URL изменился — обнови `VITE_API_URL` в Cloudflare Pages (Settings →
Environment Variables → Edit) и пересобери (Deployments → Retry latest).

### Стабильный URL вместо ephemeral (для тех, у кого есть домен в Cloudflare)

Поменяй `quick tunnel` на `named tunnel`:
```bash
ssh personal-vps
cloudflared tunnel login    # откроет браузер
cloudflared tunnel create tgmusic
cloudflared tunnel route dns tgmusic api.твойдомен.com
mkdir -p /etc/cloudflared
cat > /etc/cloudflared/config.yml <<YAML
tunnel: tgmusic
credentials-file: /root/.cloudflared/<UUID>.json
ingress:
  - hostname: api.твойдомен.com
    service: http://127.0.0.1:8080
  - service: http_status:404
YAML
# обнови ExecStart в /etc/systemd/system/cloudflared-tgmusic.service:
#   ExecStart=/usr/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run tgmusic
systemctl daemon-reload && systemctl restart cloudflared-tgmusic
```

### Регистрация Mini App в @BotFather

После того, как Pages выдаст URL фронта:

1. В Telegram: `@BotFather` → `/mybots`
2. Выбери `@spoty_wcwd_bot` → Bot Settings → Menu Button → Configure Menu Button
3. Текст кнопки: `🎵 Library`
4. URL: `https://tg-music-app.pages.dev`

Теперь при открытии бота снизу есть кнопка "🎵 Library" — тап открывает
Mini App в Telegram WebView.

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
