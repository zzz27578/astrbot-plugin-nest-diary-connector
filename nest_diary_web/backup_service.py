from __future__ import annotations

import io
import zipfile
from pathlib import Path

from nest_diary_web.paths import NestPaths


class BackupService:
    allowed_roots = {
        "system",
        "modules",
        "user_custom",
        "imports",
        # Legacy standalone layout, accepted for old backups.
        "diary",
        "memory",
        "media",
        "settings",
    }

    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.paths.ensure_all()

    def export_zip(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for root_name in ["system", "modules", "user_custom", "imports"]:
                root = self.paths.root / root_name
                if not root.exists():
                    continue
                for path in root.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(self.paths.root).as_posix())
        buffer.seek(0)
        return buffer.read()

    def import_zip(self, payload: bytes) -> dict:
        imported = 0
        skipped = 0
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                parts = Path(member.filename).parts
                if not parts or parts[0] not in self.allowed_roots or self._is_unsafe(parts):
                    skipped += 1
                    continue
                target = self.paths.root / Path(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
                imported += 1
        return {"imported": imported, "skipped": skipped}

    def _is_unsafe(self, parts: tuple[str, ...]) -> bool:
        return any(part in {"", ".", ".."} for part in parts)
