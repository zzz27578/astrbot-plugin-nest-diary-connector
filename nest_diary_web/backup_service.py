from __future__ import annotations

import io
import json
import shutil
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
            files: dict[str, Path] = {}
            legacy_sources: list[dict[str, str]] = []
            for item in package_types:
                for path in self._export_paths(item, module_id, include_security):
                    files[self._archive_name(path)] = path
                for source, archive_name in self._legacy_diary_sources(item):
                    files[archive_name] = source
                    legacy_sources.append({"archive_name": archive_name, "filename": source.name})
            manifest = {
                "package_type": package_type,
                "package_types": package_types,
                "module_id": module_id,
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "nest_version": nest_version,
                "include_security": include_security,
                "legacy_sources": legacy_sources,
                "file_count": len(files),
                "data_summary": self.data_health_summary(),
                "schema_version": 1,
            }
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for archive_name, path in sorted(files.items()):
                archive.write(path, archive_name)
        buffer.seek(0)
        return buffer.read()

    def _normalize_package_types(self, package_type: str) -> list[str]:
        aliases = {
            "webui-custom": "webui_custom",
            "webui": "webui_custom",
            "custom-module": "custom_module",
            "module": "custom_module",
            "extensions": "extension",
        }
        allowed = {
            "full",
            "diary",
            "impressions",
            "media",
            "memos",
            "webui_custom",
            "security",
            "custom_module",
            "extension",
        }
        items = [aliases.get(item.strip(), item.strip()) for item in (package_type or "full").split(",") if item.strip()]
        picked = [item for item in items if item in allowed]
        return picked or ["full"]

    def preview_zip(self, payload: bytes) -> dict:
        importable = 0
        skipped = 0
        manifest: dict = {}
        package_summary = {"file_count": 0, "roots": {}, "unsafe": []}
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if "manifest.json" in archive.namelist():
                try:
                    manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                except Exception:
                    manifest = {}
            for member in archive.infolist():
                if member.is_dir() or member.filename == "manifest.json":
                    continue
                parts = Path(member.filename).parts
                root = parts[0] if parts else ""
                package_summary["file_count"] += 1
                package_summary["roots"][root] = package_summary["roots"].get(root, 0) + 1
                if not parts or root not in self.allowed_roots or self._is_unsafe(parts) or self._is_import_backup(parts):
                    skipped += 1
                    if len(package_summary["unsafe"]) < 20:
                        package_summary["unsafe"].append(member.filename)
                    continue
                importable += 1
        return {
            "manifest": manifest,
            "package_summary": package_summary,
            "importable": importable,
            "skipped": skipped,
        }

    def import_zip(self, payload: bytes, strategy: str = "safe") -> dict:
        strategy = strategy if strategy in {"safe", "overwrite"} else "safe"
        imported = 0
        skipped = 0
        overwritten = 0
        backed_up = 0
        manifest: dict = {}
        before = self.data_health_summary()
        snapshot_path = ""
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if "manifest.json" in archive.namelist():
                try:
                    manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                except Exception:
                    manifest = {}
            backup_root = self.paths.root / "imports" / "import-backups" / self._timestamp()
            if self._has_importable_members(archive):
                snapshot_path = str(self._snapshot_before_import(backup_root))
            for member in archive.infolist():
                if member.is_dir() or member.filename == "manifest.json":
                    continue
                parts = Path(member.filename).parts
                if not parts or parts[0] not in self.allowed_roots or self._is_unsafe(parts) or self._is_import_backup(parts):
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
        after = self.data_health_summary()
        return {
            "imported": imported,
            "skipped": skipped,
            "overwritten": overwritten,
            "backed_up": backed_up,
            "strategy": strategy,
            "manifest": manifest,
            "backup_path": snapshot_path,
            "before": before,
            "after": after,
            "warnings": self._health_warnings(before, after),
        }

    def data_health_summary(self) -> dict:
        diary_files = self._files_under(self.paths.modules_dir / "diary" / "notebooks", "*.md")
        legacy_diary_files = self._files_under(self.paths.diary_dir, "*.md")
        all_diary_files = sorted(set(diary_files + legacy_diary_files))
        diary_dates = sorted(
            {
                path.stem
                for path in all_diary_files
                if self._looks_like_date(path.stem)
            }
        )
        media_manifests = self._files_under(self.paths.media_dir / "by-date", "manifest.json")
        media_assets = 0
        for manifest_path in media_manifests:
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            assets = data.get("assets")
            if isinstance(assets, list):
                media_assets += len(assets)
        memo_items = 0
        memo_path = self.paths.modules_dir / "memos" / "items.json"
        if memo_path.exists():
            try:
                data = json.loads(memo_path.read_text(encoding="utf-8"))
                items = data.get("items") if isinstance(data, dict) else data
                memo_items = len([item for item in (items or []) if isinstance(item, dict) and not item.get("deleted_at")])
            except Exception:
                memo_items = 0
        return {
            "diary_count": len(all_diary_files),
            "latest_diary_date": diary_dates[-1] if diary_dates else "",
            "latest_diary_dates": diary_dates[-7:],
            "notebook_count": self._json_item_count(self.paths.diary_notebook_registry_file),
            "impression_count": len(self._files_under(self.paths.memory_dir / "people", "*.json")),
            "media_count": media_assets,
            "memo_count": memo_items,
            "module_file_count": len(self._files_under(self.paths.modules_dir)),
            "framework_file_count": len(self._files_under(self.paths.framework_dir)),
        }

    def _export_paths(self, package_type: str, module_id: str, include_security: bool) -> list[Path]:
        if module_id and not self._is_safe_package_id(module_id):
            return []
        roots: list[Path] = []
        if package_type == "full":
            roots = [self.paths.root / "framework", self.paths.root / "modules"]
        elif package_type == "diary":
            roots = [
                self.paths.modules_dir / "diary" / "entries",
                self.paths.modules_dir / "diary" / "notebooks",
                self.paths.modules_dir / "diary" / "notebooks.json",
                self.paths.modules_dir / "diary" / "snapshots",
                self.paths.modules_dir / "diary" / "drafts",
            ]
        elif package_type == "impressions":
            roots = [self.paths.modules_dir / "impressions"]
        elif package_type == "media":
            roots = [self.paths.modules_dir / "media"]
        elif package_type == "memos":
            roots = [self.paths.modules_dir / "memos"]
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

    def _archive_name(self, path: Path) -> str:
        return path.relative_to(self.paths.root).as_posix()

    def _legacy_diary_sources(self, package_type: str) -> list[tuple[Path, str]]:
        if package_type not in {"full", "diary"}:
            return []
        candidates = [self.paths.root / "daily_diary.txt"]
        candidates.extend(parent / "daily_diary.txt" for parent in list(self.paths.root.parents)[:3])
        candidates.append(Path("/AstrBot/data/daily_diary.txt"))

        items: list[tuple[Path, str]] = []
        seen: set[str] = set()
        for candidate in candidates:
            try:
                key = str(candidate.resolve())
            except OSError:
                key = str(candidate)
            if key in seen or not candidate.is_file():
                continue
            seen.add(key)
            suffix = "" if not items else f"-{len(items) + 1}"
            items.append((candidate, f"imports/legacy-daily-diary/daily_diary{suffix}.txt"))
        return items

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _is_safe_package_id(self, value: str) -> bool:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
        return bool(value) and all(char in allowed for char in value)

    def _is_unsafe(self, parts: tuple[str, ...]) -> bool:
        return any(part in {"", ".", ".."} for part in parts)

    def _is_import_backup(self, parts: tuple[str, ...]) -> bool:
        return len(parts) >= 2 and parts[0] == "imports" and parts[1] in {"import-backups", "module-install-backups"}

    def _has_importable_members(self, archive: zipfile.ZipFile) -> bool:
        for member in archive.infolist():
            if member.is_dir() or member.filename == "manifest.json":
                continue
            parts = Path(member.filename).parts
            if parts and parts[0] in self.allowed_roots and not self._is_unsafe(parts) and not self._is_import_backup(parts):
                return True
        return False

    def _snapshot_before_import(self, backup_root: Path) -> Path:
        snapshot_root = backup_root / "before-import"
        for source_name in ["framework", "modules"]:
            source = self.paths.root / source_name
            target = snapshot_root / source_name
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            elif source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        return snapshot_root

    def _health_warnings(self, before: dict, after: dict) -> list[dict]:
        warnings: list[dict] = []
        if int(after.get("diary_count", 0)) < int(before.get("diary_count", 0)):
            warnings.append(
                {
                    "level": "danger",
                    "title": "Diary count decreased",
                    "message": f"Diary files changed from {before.get('diary_count', 0)} to {after.get('diary_count', 0)}.",
                }
            )
        before_latest = str(before.get("latest_diary_date") or "")
        after_latest = str(after.get("latest_diary_date") or "")
        if before_latest and after_latest and after_latest < before_latest:
            warnings.append(
                {
                    "level": "danger",
                    "title": "Latest diary date moved backward",
                    "message": f"Latest diary date changed from {before_latest} to {after_latest}.",
                }
            )
        return warnings

    def _files_under(self, root: Path, pattern: str = "*") -> list[Path]:
        if root.is_file():
            return [root]
        if not root.exists():
            return []
        return [path for path in root.rglob(pattern) if path.is_file()]

    def _looks_like_date(self, value: str) -> bool:
        if len(value) != 10:
            return False
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _json_item_count(self, path: Path) -> int:
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            if isinstance(data.get("items"), list):
                return len(data["items"])
            return len(data)
        return 0
