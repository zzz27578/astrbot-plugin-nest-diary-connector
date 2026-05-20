from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import re


SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_package_id(value: str, fallback: str = "default") -> str:
    cleaned = SAFE_ID_RE.sub("_", (value or "").strip()).strip("._-")
    return cleaned or fallback


@dataclass(frozen=True)
class NestPaths:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def system_dir(self) -> Path:
        return self.framework_dir

    @property
    def framework_dir(self) -> Path:
        return self.root / "framework"

    @property
    def framework_settings_dir(self) -> Path:
        return self.framework_dir / "settings"

    @property
    def framework_user_custom_dir(self) -> Path:
        return self.framework_dir / "user_custom"

    @property
    def modules_dir(self) -> Path:
        return self.root / "modules"

    @property
    def user_custom_dir(self) -> Path:
        return self.framework_user_custom_dir

    def module_dir(self, module_id: str) -> Path:
        return self.modules_dir / module_id

    def module_data_dir(self, module_id: str) -> Path:
        return self.module_dir(module_id) / "data"

    @property
    def diary_dir(self) -> Path:
        return self.modules_dir / "diary" / "entries"

    @property
    def diary_notebooks_dir(self) -> Path:
        return self.modules_dir / "diary" / "notebooks"

    @property
    def diary_notebook_registry_file(self) -> Path:
        return self.modules_dir / "diary" / "notebooks.json"

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
        return self.framework_settings_dir

    def diary_file(self, date: str) -> Path:
        return self.diary_file_for_notebook("default", date)

    def diary_entries_dir_for_notebook(self, notebook_id: str) -> Path:
        notebook_id = safe_package_id(notebook_id)
        return self.diary_notebooks_dir / notebook_id / "entries"

    def diary_file_for_notebook(self, notebook_id: str, date: str) -> Path:
        notebook_id = safe_package_id(notebook_id)
        year, month, _day = date.split("-")
        return self.diary_entries_dir_for_notebook(notebook_id) / year / month / f"{date}.md"

    def revision_dir_for_notebook(self, notebook_id: str, date: str) -> Path:
        notebook_id = safe_package_id(notebook_id)
        return self.revisions_dir / notebook_id / date[:4] / date[5:7] / date

    def ensure_all(self) -> None:
        for path in [
            self.framework_dir,
            self.framework_settings_dir,
            self.framework_dir / "cache",
            self.framework_dir / "logs",
            self.modules_dir,
            self.user_custom_dir / "webui" / "themes",
            self.user_custom_dir / "webui" / "modules",
            self.user_custom_dir / "webui" / "extensions",
            self.diary_dir,
            self.diary_notebooks_dir / "default" / "entries",
            self.memory_dir / "people",
            self.memory_dir / "topics",
            self.memory_dir / "events",
            self.modules_dir / "extensions",
            self.modules_dir / "archive" / "monthly",
            self.modules_dir / "archive" / "yearly",
            self.media_dir / "blobs" / "sha256",
            self.media_dir / "variants",
            self.media_dir / "by-date",
            self.modules_dir / "diary" / "drafts",
            self.revisions_dir,
            self.root / "imports",
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
            (self.root / "system" / "settings", self.settings_dir),
            (self.root / "settings", self.settings_dir),
            (self.root / "user_custom", self.user_custom_dir),
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
