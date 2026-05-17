from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from nest_diary_web.models import PersonImpression
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

        impression.confidence = max(1, min(int(impression.confidence), 5))
        path = self._person_path(impression.name)
        path.write_text(
            json.dumps(asdict(impression), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return impression

    def get(self, name: str) -> PersonImpression | None:
        path = self._person_path(name)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return PersonImpression(
            name=data["name"],
            summary=data.get("summary", ""),
            traits=data.get("traits", []),
            interests=data.get("interests", []),
            preferences=data.get("preferences", []),
            relationship=data.get("relationship", ""),
            evidence_dates=data.get("evidence_dates", []),
            confidence=data.get("confidence", 3),
            notes=data.get("notes", ""),
            updated_at=data.get("updated_at", ""),
        )

    def list_people(self) -> list[PersonImpression]:
        people: list[PersonImpression] = []
        for path in sorted(self.people_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                people.append(
                    PersonImpression(
                        name=data["name"],
                        summary=data.get("summary", ""),
                        traits=data.get("traits", []),
                        interests=data.get("interests", []),
                        preferences=data.get("preferences", []),
                        relationship=data.get("relationship", ""),
                        evidence_dates=data.get("evidence_dates", []),
                        confidence=data.get("confidence", 3),
                        notes=data.get("notes", ""),
                        updated_at=data.get("updated_at", ""),
                    )
                )
            except Exception:
                continue
        return sorted(people, key=lambda item: item.updated_at, reverse=True)

    def _person_path(self, name: str) -> Path:
        safe_name = quote(name.strip(), safe="")
        return self.people_dir / f"{safe_name}.json"

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
