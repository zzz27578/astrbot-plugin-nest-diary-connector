from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from nest_diary_web.models import DiaryEntry, PersonImpression
from nest_diary_web.paths import NestPaths


class ImpressionService:
    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.paths.ensure_all()
        self.people_dir.mkdir(parents=True, exist_ok=True)

    @property
    def people_dir(self) -> Path:
        return self.paths.memory_dir / "people"

    def save(self, impression: PersonImpression) -> PersonImpression:
        current = self.get(impression.name)
        if current and not impression.updated_at:
            impression.updated_at = self._now()
        elif not impression.updated_at:
            impression.updated_at = self._now()

        impression.name = impression.name.strip()
        if not impression.name:
            raise ValueError("Person name is required")
        impression.summary = impression.summary.strip()
        impression.identity = impression.identity.strip()
        impression.relationship = impression.relationship.strip()
        impression.special_comment = impression.special_comment.strip()
        impression.notes = impression.notes.strip()
        impression.affinity = max(1, min(int(impression.affinity), 5))
        impression.confidence = max(1, min(int(impression.confidence), 5))
        path = self._person_path(impression.name)
        path.write_text(
            json.dumps(asdict(impression), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return impression

    def delete(self, name: str) -> bool:
        path = self._person_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def get(self, name: str) -> PersonImpression | None:
        path = self._person_path(name)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._from_dict(data)

    def list_people(self) -> list[PersonImpression]:
        people: list[PersonImpression] = []
        for path in sorted(self.people_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                people.append(self._from_dict(data))
            except Exception:
                continue
        return sorted(people, key=lambda item: item.updated_at, reverse=True)

    def touch_from_diary(
        self,
        entry: DiaryEntry,
        *,
        allow_new_people: bool = False,
        update_existing: bool = False,
        min_confidence: int = 3,
    ) -> list[PersonImpression]:
        if not allow_new_people and not update_existing:
            return []
        touched: list[PersonImpression] = []
        min_confidence = max(1, min(int(min_confidence), 5))
        for raw_name in entry.people:
            name = raw_name.strip()
            if not name:
                continue
            current = self.get(name)
            if current:
                if not update_existing:
                    continue
                changed = False
                if entry.date not in current.evidence_dates:
                    current.evidence_dates.append(entry.date)
                    changed = True
                if changed:
                    current.notes = self._append_auto_note(current.notes, entry.date, "自动补充证据")
                    touched.append(self.save(current))
                continue
            if not allow_new_people:
                continue
            touched.append(
                self.save(
                    PersonImpression(
                        name=name,
                        summary=self._auto_summary(name, entry.date, min_confidence),
                        evidence_dates=[entry.date],
                        confidence=min_confidence,
                        notes=self._append_auto_note("", entry.date, "自动候选建档"),
                    )
                )
            )
        return touched

    def _from_dict(self, data: dict) -> PersonImpression:
        return PersonImpression(
            name=data["name"],
            summary=data.get("summary", ""),
            identity=data.get("identity", ""),
            traits=data.get("traits", []),
            hobbies=data.get("hobbies", []),
            interests=data.get("interests", []),
            preferences=data.get("preferences", []),
            relationship=data.get("relationship", ""),
            affinity=data.get("affinity", 3),
            special_comment=data.get("special_comment", ""),
            evidence_dates=data.get("evidence_dates", []),
            confidence=data.get("confidence", 3),
            notes=data.get("notes", ""),
            updated_at=data.get("updated_at", ""),
        )

    def _person_path(self, name: str) -> Path:
        safe_name = quote(name.strip(), safe="")
        return self.people_dir / f"{safe_name}.json"

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _auto_summary(self, name: str, date: str, confidence: int) -> str:
        return (
            f"{name} 在 {date} 的日记中被记录为相关人物。"
            f"这是按当前印象策略生成的候选档案，置信度 {confidence}/5；"
            "需要后续日记和 bot 主观评价补充后，才应写入稳定印象。"
        )

    def _append_auto_note(self, notes: str, date: str, reason: str) -> str:
        marker = f"{reason}：该人物出现在 {date} 的日记关联人物中。"
        if marker in notes:
            return notes
        return f"{notes.rstrip()}\n{marker}".strip()
