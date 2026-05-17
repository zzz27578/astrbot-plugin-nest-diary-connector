from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from nest_diary_web.models import DiaryEntry
from nest_diary_web.paths import NestPaths


@dataclass(frozen=True)
class SearchCapabilities:
    fts5: bool
    backend: str


class SearchService:
    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.paths.ensure_all()
        self.db_path = self.paths.index_dir / "nest.sqlite"
        self.capabilities = SearchCapabilities(fts5=False, backend="sqlite-like")
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
            try:
                fts_columns = [row[1] for row in conn.execute("PRAGMA table_info(diary_fts)").fetchall()]
                if fts_columns and fts_columns != ["date", "title", "body", "tags", "people", "mood"]:
                    conn.execute("DROP TABLE diary_fts")
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS diary_fts
                    USING fts5(date UNINDEXED, title, body, tags, people, mood)
                    """
                )
                self.capabilities = SearchCapabilities(fts5=True, backend="sqlite-fts5-bm25")
                count = conn.execute("SELECT COUNT(*) FROM diary_fts").fetchone()[0]
                if count == 0:
                    conn.execute(
                        """
                        INSERT INTO diary_fts(date, title, body, tags, people, mood)
                        SELECT date, title, body, tags, people, mood FROM diary_meta
                        """
                    )
            except sqlite3.OperationalError:
                self.capabilities = SearchCapabilities(fts5=False, backend="sqlite-like")

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
            if self.capabilities.fts5:
                conn.execute("DELETE FROM diary_fts WHERE date = ?", (entry.date,))
                conn.execute(
                    "INSERT INTO diary_fts(date, title, body, tags, people, mood) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        entry.date,
                        entry.normalized_title(),
                        entry.body,
                        " ".join(entry.tags),
                        " ".join(entry.people),
                        " ".join(entry.mood),
                    ),
                )

    def delete_entry(self, date: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM diary_meta WHERE date = ?", (date,))
            if self.capabilities.fts5:
                conn.execute("DELETE FROM diary_fts WHERE date = ?", (date,))

    def search(self, query: str, top_k: int = 8, snippet_chars: int = 180) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        top_k = max(1, min(int(top_k), 20))
        snippet_chars = max(80, min(int(snippet_chars), 360))
        with self._connect() as conn:
            rows = []
            if self.capabilities.fts5:
                match_query = self._match_query(query)
                try:
                    rows = conn.execute(
                        """
                        SELECT
                            f.date,
                            m.title,
                            snippet(diary_fts, 2, '[', ']', '...', 18),
                            bm25(diary_fts, 3.0, 1.5, 1.0, 1.2, 1.2, 0.8) AS score,
                            m.tags,
                            m.people,
                            'fts5'
                        FROM diary_fts f
                        JOIN diary_meta m ON m.date = f.date
                        WHERE diary_fts MATCH ?
                        ORDER BY score
                        LIMIT ?
                        """,
                        (match_query, top_k),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            if rows:
                return [
                    {
                        "date": row[0],
                        "title": row[1],
                        "snippet": self._trim_snippet(row[2], snippet_chars),
                        "score": row[3],
                        "tags": self._split_csv(row[4]),
                        "people": self._split_csv(row[5]),
                        "backend": row[6],
                    }
                    for row in rows
                ]

            tokens = self._tokens(query)
            if tokens:
                where_parts = []
                params: list[str | int] = []
                for token in tokens:
                    like_query = f"%{token}%"
                    where_parts.append(
                        "(date LIKE ? OR body LIKE ? OR title LIKE ? OR tags LIKE ? OR people LIKE ? OR mood LIKE ?)"
                    )
                    params.extend([like_query, like_query, like_query, like_query, like_query, like_query])
                rows = conn.execute(
                    """
                    SELECT date, title, body, tags, people
                    FROM diary_meta
                    WHERE """ + " AND ".join(where_parts) + """
                    ORDER BY date DESC
                    LIMIT ?
                    """,
                    (*params, top_k),
                ).fetchall()
            else:
                rows = []
            if rows:
                return [
                    {
                        "date": row[0],
                        "title": row[1],
                        "snippet": self._make_snippet(row[2], query, snippet_chars),
                        "score": None,
                        "tags": self._split_csv(row[3]),
                        "people": self._split_csv(row[4]),
                        "backend": "sqlite-like",
                    }
                    for row in rows
                ]

            like_query = f"%{query}%"
            rows = conn.execute(
                """
                SELECT date, title, body, tags, people
                FROM diary_meta
                WHERE date LIKE ? OR body LIKE ? OR title LIKE ? OR tags LIKE ? OR people LIKE ? OR mood LIKE ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (like_query, like_query, like_query, like_query, like_query, like_query, top_k),
            ).fetchall()
            return [
                {
                    "date": row[0],
                    "title": row[1],
                    "snippet": self._make_snippet(row[2], query, snippet_chars),
                    "score": None,
                    "tags": self._split_csv(row[3]),
                    "people": self._split_csv(row[4]),
                    "backend": "sqlite-like",
                }
                for row in rows
            ]

    def _match_query(self, query: str) -> str:
        tokens = self._tokens(query)
        if not tokens:
            return f'"{query.replace(chr(34), chr(34) + chr(34))}"'
        return " OR ".join(f'"{token.replace(chr(34), chr(34) + chr(34))}"' for token in tokens)

    def _tokens(self, query: str) -> list[str]:
        normalized = query.replace("，", " ").replace("、", " ").replace(",", " ")
        return [token.strip() for token in normalized.split() if token.strip()]

    def _split_csv(self, value: str) -> list[str]:
        return [item for item in value.split(",") if item]

    def _trim_snippet(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def _make_snippet(self, text: str, query: str, limit: int = 180) -> str:
        candidates = [query, *self._tokens(query)]
        positions = [text.find(item) for item in candidates if item and text.find(item) >= 0]
        if not positions:
            return self._trim_snippet(text, limit)
        index = min(positions)
        start = max(index - limit // 3, 0)
        end = min(start + limit, len(text))
        return self._trim_snippet(text[start:end], limit)
