from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id            TEXT    NOT NULL,
    file_unique_id     TEXT    NOT NULL UNIQUE,
    title              TEXT,
    artist             TEXT,
    album              TEXT,
    duration_s         INTEGER,
    file_name          TEXT,
    mime_type          TEXT,
    file_size          INTEGER,
    thumb_file_id      TEXT,
    source_chat_id     INTEGER,
    source_message_id  INTEGER,
    added_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
CREATE INDEX IF NOT EXISTS idx_tracks_album  ON tracks(album);
CREATE INDEX IF NOT EXISTS idx_tracks_title  ON tracks(title);
"""


@dataclass(slots=True)
class Track:
    id: int
    file_id: str
    file_unique_id: str
    title: str | None
    artist: str | None
    album: str | None
    duration_s: int | None
    file_name: str | None
    mime_type: str | None
    thumb_file_id: str | None

    @property
    def display(self) -> str:
        artist = self.artist or "Unknown Artist"
        title = self.title or self.file_name or "Untitled"
        mins, secs = divmod(self.duration_s or 0, 60)
        return f"{artist} — {title} [{mins}:{secs:02d}]"


class DB:
    def __init__(self, path: str | Path):
        self.path = str(path)

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()

    async def upsert_track(
        self,
        *,
        file_id: str,
        file_unique_id: str,
        title: str | None,
        artist: str | None,
        album: str | None,
        duration_s: int | None,
        file_name: str | None,
        mime_type: str | None,
        file_size: int | None,
        thumb_file_id: str | None,
        source_chat_id: int | None,
        source_message_id: int | None,
    ) -> tuple[int, bool]:
        """Insert track if new, refresh file_id if seen before.

        Returns (track_id, was_new).
        """
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            existing = await conn.execute(
                "SELECT id FROM tracks WHERE file_unique_id = ?",
                (file_unique_id,),
            )
            row = await existing.fetchone()
            if row is not None:
                # Refresh file_id (it can rotate) but keep the original record.
                await conn.execute(
                    "UPDATE tracks SET file_id = ? WHERE id = ?",
                    (file_id, row["id"]),
                )
                await conn.commit()
                return row["id"], False

            cursor = await conn.execute(
                """
                INSERT INTO tracks (
                    file_id, file_unique_id, title, artist, album,
                    duration_s, file_name, mime_type, file_size,
                    thumb_file_id, source_chat_id, source_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id, file_unique_id, title, artist, album,
                    duration_s, file_name, mime_type, file_size,
                    thumb_file_id, source_chat_id, source_message_id,
                ),
            )
            await conn.commit()
            return cursor.lastrowid, True

    async def get(self, track_id: int) -> Track | None:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM tracks WHERE id = ?", (track_id,)
            )
            row = await cursor.fetchone()
            return _row_to_track(row) if row else None

    async def recent(self, limit: int = 10) -> list[Track]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM tracks ORDER BY added_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [_row_to_track(r) for r in rows]

    async def search(self, query: str, limit: int = 20) -> list[Track]:
        like = f"%{query}%"
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT * FROM tracks
                WHERE title     LIKE ? COLLATE NOCASE
                   OR artist    LIKE ? COLLATE NOCASE
                   OR album     LIKE ? COLLATE NOCASE
                   OR file_name LIKE ? COLLATE NOCASE
                ORDER BY added_at DESC
                LIMIT ?
                """,
                (like, like, like, like, limit),
            )
            rows = await cursor.fetchall()
            return [_row_to_track(r) for r in rows]

    async def counts(self) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as conn:
            tracks = await (await conn.execute(
                "SELECT COUNT(*) FROM tracks"
            )).fetchone()
            artists = await (await conn.execute(
                "SELECT COUNT(DISTINCT artist) FROM tracks WHERE artist IS NOT NULL"
            )).fetchone()
            albums = await (await conn.execute(
                "SELECT COUNT(DISTINCT album) FROM tracks WHERE album IS NOT NULL"
            )).fetchone()
            duration = await (await conn.execute(
                "SELECT COALESCE(SUM(duration_s), 0) FROM tracks"
            )).fetchone()
            return {
                "tracks": tracks[0] if tracks else 0,
                "artists": artists[0] if artists else 0,
                "albums": albums[0] if albums else 0,
                "total_seconds": duration[0] if duration else 0,
            }

    async def top_artists(self, limit: int = 30) -> list[tuple[str, int]]:
        async with aiosqlite.connect(self.path) as conn:
            cursor = await conn.execute(
                """
                SELECT artist, COUNT(*) AS n
                FROM tracks
                WHERE artist IS NOT NULL AND artist != ''
                GROUP BY artist
                ORDER BY n DESC, artist ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [(row[0], row[1]) for row in await cursor.fetchall()]


def _row_to_track(row: aiosqlite.Row) -> Track:
    return Track(
        id=row["id"],
        file_id=row["file_id"],
        file_unique_id=row["file_unique_id"],
        title=row["title"],
        artist=row["artist"],
        album=row["album"],
        duration_s=row["duration_s"],
        file_name=row["file_name"],
        mime_type=row["mime_type"],
        thumb_file_id=row["thumb_file_id"],
    )
