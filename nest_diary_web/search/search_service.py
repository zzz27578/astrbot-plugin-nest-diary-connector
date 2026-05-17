from __future__ import annotations

import sqlite3

from nest_diary_web.models import DiaryEntry
from nest_diary_web.paths import NestPaths


class SearchService:
    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.paths.ensure_all()
        self.db_path = self.paths.index_dir / "nest.sqlite"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS diary_meta (
                    date TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL,
                    people TEXT NOT NULL,
                    mood TEXT NOT NULL,
                    importance INTEGER NOT NULL,
                    source TEXT NOT NULL
                )
                """
            )
            columns = [row[1] for row in conn.execute("PRAGMA table_info(diary_meta)").fetchall()]
            if "body" not in columns:
                conn.execute("ALTER TABLE diary_meta ADD COLUMN body TEXT NOT NULL DEFAULT ''")
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS diary_fts
                USING fts5(date UNINDEXED, title, body)
                """
            )

    def upsert_entry(self, entry: DiaryEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO diary_meta
                (date, title, body, tags, people, mood, importance, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.date,
                    entry.normalized_title(),
                    entry.body,
                    ",".join(entry.tags),
                    ",".join(entry.people),
                    ",".join(entry.mood),
                    entry.importance,
                    entry.source,
                ),
            )
            conn.execute("DELETE FROM diary_fts WHERE date = ?", (entry.date,))
            conn.execute(
                "INSERT INTO diary_fts(date, title, body) VALUES (?, ?, ?)",
                (entry.date, entry.normalized_title(), entry.body),
            )

    def delete_entry(self, date: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM diary_meta WHERE date = ?", (date,))
            conn.execute("DELETE FROM diary_fts WHERE date = ?", (date,))

    def search(self, query: str, top_k: int = 8) -> list[dict]:
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT date, title, snippet(diary_fts, 2, '[', ']', '...', 18)
                    FROM diary_fts
                    WHERE diary_fts MATCH ?
                    LIMIT ?
                    """,
                    (query, top_k),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            if not rows:
                like_query = f"%{query}%"
                rows = conn.execute(
                    """
                    SELECT date, title, body
                    FROM diary_meta
                    WHERE date LIKE ? OR body LIKE ? OR title LIKE ? OR tags LIKE ? OR people LIKE ?
                    LIMIT ?
                    """,
                    (like_query, like_query, like_query, like_query, like_query, top_k),
                ).fetchall()
                return [
                    {"date": row[0], "title": row[1], "snippet": self._make_snippet(row[2], query)}
                    for row in rows
                ]
        return [{"date": row[0], "title": row[1], "snippet": row[2]} for row in rows]

    def _make_snippet(self, text: str, query: str) -> str:
        index = text.find(query)
        if index < 0:
            return text[:80]
        start = max(index - 24, 0)
        end = min(index + len(query) + 48, len(text))
        return text[start:end]
