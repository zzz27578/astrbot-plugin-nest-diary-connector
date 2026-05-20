from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from nest_diary_web.paths import NestPaths


class BackupService:
    allowed_roots = {
        "framework",
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

    def export_zip(
        self,
        package_type: str = "full",
        module_id: str = "",
        include_security: bool = False,
        nest_version: str = "",
    ) -> bytes:
        package_types = self._normalize_package_types(package_type)
        package_type = package_types[0] if len(package_types) == 1 else "selected"
        module_id = (module_id or "").strip()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                "package_type": package_type,
                "package_types": package_types,
                "module_id": module_id,
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "nest_version": nest_version,
                "include_security": include_security,
                "schema_version": 1,
            }
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            files: set[Path] = set()
            for item in package_types:
                files.update(self._export_paths(item, module_id, include_security))
            for path in sorted(files):
                archive.write(path, path.relative_to(self.paths.root).as_posix())
        buffer.seek(0)
        return buffer.read()

    def _normalize_package_types(self, package_type: str) -> list[str]:
        allowed = {
            "full",
            "diary",
            "impressions",
            "media",
            "webui_custom",
            "security",
            "custom_module",
            "extension",
        }
        items = [item.strip() for item in (package_type or "full").split(",") if item.strip()]
        picked = [item for item in items if item in allowed]
        return picked or ["full"]

    def import_zip(self, payload: bytes, strategy: str = "safe") -> dict:
        strategy = strategy if strategy in {"safe", "overwrite"} else "safe"
        imported = 0
        skipped = 0
        overwritten = 0
        backed_up = 0
        manifest: dict = {}
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if "manifest.json" in archive.namelist():
                try:
                    manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                except Exception:
                    manifest = {}
            backup_root = self.paths.root / "imports" / "import-backups" / self._timestamp()
            for member in archive.infolist():
                if member.is_dir() or member.filename == "manifest.json":
                    continue
                parts = Path(member.filename).parts
                if not parts or parts[0] not in self.allowed_roots or self._is_unsafe(parts):
                    skipped += 1
                    continue
                target = self.paths.root / Path(*parts)
                if target.exists() and strategy == "safe":
                    skipped += 1
                    continue
                if target.exists() and strategy == "overwrite":
                    backup_target = backup_root / Path(*parts)
                    backup_target.parent.mkdir(parents=True, exist_ok=True)
                    backup_target.write_bytes(target.read_bytes())
                    backed_up += 1
                    overwritten += 1
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
                imported += 1
        self.paths.migrate_legacy_layout()
        return {
            "imported": imported,
            "skipped": skipped,
            "overwritten": overwritten,
            "backed_up": backed_up,
            "strategy": strategy,
            "manifest": manifest,
        }

    def _export_paths(self, package_type: str, module_id: str, include_security: bool) -> list[Path]:
        if module_id and not self._is_safe_package_id(module_id):
            return []
        roots: list[Path] = []
        if package_type == "full":
            roots = [self.paths.root / "framework", self.paths.root / "modules", self.paths.root / "imports"]
        elif package_type == "diary":
            roots = [
                self.paths.modules_dir / "diary" / "entries",
                self.paths.modules_dir / "diary" / "snapshots",
                self.paths.modules_dir / "diary" / "drafts",
            ]
        elif package_type == "impressions":
            roots = [self.paths.modules_dir / "impressions"]
        elif package_type == "media":
            roots = [self.paths.modules_dir / "media"]
        elif package_type == "webui_custom":
            roots = [
                self.paths.framework_dir / "assets",
                self.paths.user_custom_dir / "webui",
                self.paths.settings_dir / "service-ui.json",
            ]
        elif package_type == "custom_module" and module_id:
            roots = [
                self.paths.modules_dir / module_id,
                self.paths.user_custom_dir / "webui" / "modules" / module_id,
            ]
        elif package_type == "extension" and module_id:
            roots = [
                self.paths.modules_dir / "extensions" / module_id,
                self.paths.user_custom_dir / "webui" / "extensions" / module_id,
            ]
        elif package_type == "security":
            roots = [self.paths.settings_dir / "security.json"]

        files: list[Path] = []
        for root in roots:
            if root.is_file():
                files.append(root)
            elif root.exists():
                files.extend(path for path in root.rglob("*") if path.is_file())
        if not include_security and package_type != "security":
            security_path = self.paths.settings_dir / "security.json"
            files = [path for path in files if path != security_path]
        return sorted(set(files))

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _is_safe_package_id(self, value: str) -> bool:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
        return bool(value) and all(char in allowed for char in value)

    def _is_unsafe(self, parts: tuple[str, ...]) -> bool:
        return any(part in {"", ".", ".."} for part in parts)
