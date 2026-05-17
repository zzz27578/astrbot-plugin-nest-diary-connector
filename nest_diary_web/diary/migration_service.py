from __future__ import annotations

import re

from nest_diary_web.models import DiaryEntry

BRACKET_DATE_RE = re.compile(r"^\[(?P<date>\d{4}-\d{2}-\d{2})\s+[^\]]+\]\s*$")
INLINE_DATE_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\s*[:：]\s*(?P<body>.*)$")


class LegacyDiaryImporter:
    """Parse the old daily_diary.txt format into dated diary entries."""

    def parse(self, text: str) -> list[DiaryEntry]:
        entries: list[DiaryEntry] = []
        current_date: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_date, current_lines
            if current_date and current_lines:
                body = "\n".join(line.rstrip() for line in current_lines).strip()
                if body:
                    entries.append(
                        DiaryEntry(
                            date=current_date,
                            title=current_date,
                            body=body,
                            source="legacy_import",
                        )
                    )
            current_date = None
            current_lines = []

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            bracket_match = BRACKET_DATE_RE.match(line)
            inline_match = INLINE_DATE_RE.match(line)

            if bracket_match:
                flush()
                current_date = bracket_match.group("date")
                current_lines = []
                continue

            if inline_match:
                flush()
                current_date = inline_match.group("date")
                current_lines = [inline_match.group("body")]
                continue

            if current_date:
                current_lines.append(line)

        flush()
        return entries
