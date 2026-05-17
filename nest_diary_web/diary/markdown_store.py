from __future__ import annotations

import json
from pathlib import Path

from nest_diary_web.models import DiaryEntry
from nest_diary_web.paths import NestPaths


class MarkdownDiaryStore:
    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.paths.ensure_all()

    def write(self, entry: DiaryEntry) -> Path:
        path = self.paths.diary_file(entry.date)
        path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter = {
            "date": entry.date,
            "title": entry.normalized_title(),
            "mood": entry.mood,
            "tags": entry.tags,
            "people": entry.people,
            "media_refs": entry.media_refs,
            "importance": entry.importance,
            "source": entry.source,
            "revision": entry.revision,
        }
        lines = ["---"]
        for key, value in frontmatter.items():
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        lines.extend(["---", "", f"# {entry.normalized_title()}", "", entry.body.rstrip(), ""])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def read(self, date: str) -> DiaryEntry:
        path = self.paths.diary_file(date)
        text = path.read_text(encoding="utf-8")
        _prefix, meta_text, body_text = text.split("---", 2)
        meta = {}
        for line in meta_text.strip().splitlines():
            key, raw_value = line.split(":", 1)
            meta[key.strip()] = json.loads(raw_value.strip())

        body_lines = body_text.strip().splitlines()
        if body_lines and body_lines[0].startswith("# "):
            body_lines = body_lines[1:]
        body = "\n".join(body_lines).strip()
        return DiaryEntry(
            date=meta["date"],
            title=meta.get("title"),
            mood=meta.get("mood", []),
            tags=meta.get("tags", []),
            people=meta.get("people", []),
            media_refs=meta.get("media_refs", []),
            importance=meta.get("importance", 3),
            source=meta.get("source", "bot"),
            revision=meta.get("revision", 1),
            body=body,
        )

    def list_entries(self) -> list[DiaryEntry]:
        entries: list[DiaryEntry] = []
        for path in sorted(self.paths.diary_dir.glob("*/*/*.md"), reverse=True):
            try:
                entries.append(self.read(path.stem))
            except Exception:
                continue
        return entries

    def delete(self, date: str) -> bool:
        path = self.paths.diary_file(date)
        if not path.exists():
            return False
        path.unlink()
        return True

    def archive_tree(self) -> list[dict]:
        years: list[dict] = []
        if not self.paths.diary_dir.exists():
            return years
        for year_dir in sorted(self.paths.diary_dir.iterdir(), reverse=True):
            if not year_dir.is_dir():
                continue
            months = []
            for month_dir in sorted(year_dir.iterdir(), reverse=True):
                if not month_dir.is_dir():
                    continue
                days = []
                for path in sorted(month_dir.glob("*.md"), reverse=True):
                    try:
                        entry = self.read(path.stem)
                    except Exception:
                        continue
                    days.append(
                        {
                            "date": entry.date,
                            "title": entry.normalized_title(),
                            "importance": entry.importance,
                            "tags": entry.tags,
                            "people": entry.people,
                        }
                    )
                if days:
                    months.append({"month": month_dir.name, "days": days, "count": len(days)})
            if months:
                years.append(
                    {
                        "year": year_dir.name,
                        "months": months,
                        "count": sum(month["count"] for month in months),
                    }
                )
        return years
