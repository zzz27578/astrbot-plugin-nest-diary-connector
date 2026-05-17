from __future__ import annotations

from nest_diary_web.diary.markdown_store import MarkdownDiaryStore
from nest_diary_web.diary.revision_service import RevisionService
from nest_diary_web.models import DiaryEntry
from nest_diary_web.paths import NestPaths
from nest_diary_web.search.search_service import SearchService


class DiaryService:
    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.store = MarkdownDiaryStore(paths)
        self.search_service = SearchService(paths)
        self.revisions = RevisionService(paths)

    def write_diary(self, entry: DiaryEntry, reason: str = "") -> DiaryEntry:
        diary_path = self.paths.diary_file(entry.date)
        if diary_path.exists():
            self.revisions.snapshot(
                date=entry.date,
                content=diary_path.read_text(encoding="utf-8"),
                reason=reason or "overwrite diary entry",
                source="write_diary",
            )
        self.store.write(entry)
        self.search_service.upsert_entry(entry)
        return entry

    def read_by_date(self, date: str) -> DiaryEntry:
        return self.store.read(date)

    def delete_diary(self, date: str, reason: str = "") -> bool:
        diary_path = self.paths.diary_file(date)
        if not diary_path.exists():
            return False
        self.revisions.snapshot(
            date=date,
            content=diary_path.read_text(encoding="utf-8"),
            reason=reason or "delete diary entry",
            source="delete_diary",
        )
        deleted = self.store.delete(date)
        self.search_service.delete_entry(date)
        return deleted

    def search(self, query: str, top_k: int = 8, snippet_chars: int = 180) -> list[dict]:
        return self.search_service.search(query=query, top_k=top_k, snippet_chars=snippet_chars)

    def search_status(self) -> dict:
        capabilities = self.search_service.capabilities
        return {"backend": capabilities.backend, "fts5": capabilities.fts5}

    def list_entries(self) -> list[DiaryEntry]:
        return self.store.list_entries()

    def archive_tree(self) -> list[dict]:
        return self.store.archive_tree()

    def rebuild_index(self) -> int:
        entries = self.store.list_entries()
        for entry in entries:
            self.search_service.upsert_entry(entry)
        return len(entries)
