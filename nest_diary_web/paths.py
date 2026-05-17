from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass(frozen=True)
class NestPaths:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def system_dir(self) -> Path:
        return self.root / "system"

    @property
    def modules_dir(self) -> Path:
        return self.root / "modules"

    @property
    def user_custom_dir(self) -> Path:
        return self.root / "user_custom"

    @property
    def diary_dir(self) -> Path:
        return self.modules_dir / "diary" / "entries"

    @property
    def index_dir(self) -> Path:
        return self.modules_dir / "diary" / "index"

    @property
    def memory_dir(self) -> Path:
        return self.modules_dir / "impressions"

    @property
    def media_dir(self) -> Path:
        return self.modules_dir / "media"

    @property
    def revisions_dir(self) -> Path:
        return self.modules_dir / "diary" / "snapshots"

    @property
    def settings_dir(self) -> Path:
        return self.system_dir / "settings"

    def diary_file(self, date: str) -> Path:
        year, month, _day = date.split("-")
        return self.diary_dir / year / month / f"{date}.md"

    def ensure_all(self) -> None:
        for path in [
            self.system_dir,
            self.modules_dir,
            self.user_custom_dir / "webui" / "themes",
            self.user_custom_dir / "webui" / "modules",
            self.diary_dir,
            self.memory_dir / "people",
            self.memory_dir / "topics",
            self.memory_dir / "events",
            self.modules_dir / "archive" / "monthly",
            self.modules_dir / "archive" / "yearly",
            self.media_dir / "blobs" / "sha256",
            self.media_dir / "variants",
            self.media_dir / "by-date",
            self.modules_dir / "diary" / "drafts",
            self.revisions_dir,
            self.root / "imports",
            self.root / "logs",
            self.settings_dir,
            self.index_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        self.migrate_legacy_layout()

    def migrate_legacy_layout(self) -> None:
        legacy_pairs = [
            (self.root / "diary", self.diary_dir),
            (self.root / "memory", self.memory_dir),
            (self.root / "media", self.media_dir),
            (self.root / "index", self.index_dir),
            (self.root / "settings", self.settings_dir),
            (self.root / "revisions" / "diary", self.revisions_dir),
        ]
        for source, target in legacy_pairs:
            if not source.exists() or source == target:
                continue
            self._copy_missing(source, target)

    def _copy_missing(self, source: Path, target: Path) -> None:
        for item in source.rglob("*"):
            relative = item.relative_to(source)
            destination = target / relative
            if item.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            elif item.is_file() and not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)
