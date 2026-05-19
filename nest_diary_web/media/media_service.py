from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from datetime import datetime, timezone
from pathlib import Path

from nest_diary_web.paths import NestPaths

try:
    from PIL import Image
except Exception:  # pragma: no cover - Pillow is optional at runtime.
    Image = None


class MediaService:
    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.paths.ensure_all()

    def save_media(
        self,
        source_path: Path,
        date: str,
        original_name: str | None = None,
        note: str | None = None,
        storage_strategy: str = "copy",
    ) -> dict:
        source = Path(source_path)
        digest = self._sha256(source)
        suffix = source.suffix.lower()
        blob_path = self._blob_path(digest, suffix)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        strategy = "move" if storage_strategy in {"move", "cut"} else "copy"
        if not blob_path.exists():
            if strategy == "move":
                shutil.move(str(source), blob_path)
            else:
                shutil.copy2(source, blob_path)
        elif strategy == "move" and self._different_paths(source, blob_path):
            source.unlink(missing_ok=True)

        manifest_path = self._manifest_path(date)
        manifest = self._read_manifest(manifest_path, date)
        record = {
            "sha256": digest,
            "path": str(blob_path),
            "url": f"/media/blobs/{digest}",
            "original_name": original_name or source.name,
            "date": date,
            "note": (note or "").strip(),
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "storage_strategy": strategy,
        }
        record.update(self._file_metadata(blob_path))
        existing = next((item for item in manifest["assets"] if item["sha256"] == digest), None)
        if existing:
            existing.update({key: value for key, value in record.items() if value not in ("", None)})
            record = existing
        else:
            manifest["assets"].append(record)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def _sha256(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _blob_path(self, digest: str, suffix: str) -> Path:
        return self.paths.media_dir / "blobs" / "sha256" / digest[:2] / digest[2:4] / f"{digest}{suffix}"

    def _manifest_path(self, date: str) -> Path:
        year, month, _day = date.split("-")
        return self.paths.media_dir / "by-date" / year / month / date / "manifest.json"

    def _read_manifest(self, path: Path, date: str) -> dict:
        if not path.exists():
            return {"date": date, "assets": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def list_manifests(self) -> list[dict]:
        root = self.paths.media_dir / "by-date"
        if not root.exists():
            return []
        manifests = []
        for path in sorted(root.glob("*/*/*/manifest.json"), reverse=True):
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest["assets"] = [
                    self._with_output_metadata(asset, manifest.get("date", "")) for asset in manifest.get("assets", [])
                ]
                manifests.append(manifest)
            except Exception:
                continue
        return manifests

    def list_by_date(self, date: str) -> dict:
        manifest = self._read_manifest(self._manifest_path(date), date)
        manifest["assets"] = [self._with_output_metadata(asset, date) for asset in manifest.get("assets", [])]
        return manifest

    def find_blob(self, digest: str) -> Path | None:
        root = self.paths.media_dir / "blobs" / "sha256" / digest[:2] / digest[2:4]
        if not root.exists():
            return None
        matches = list(root.glob(f"{digest}.*"))
        return matches[0] if matches else None

    def find_asset(self, media_ref: str = "", date: str = "", original_name: str = "") -> dict | None:
        ref = (media_ref or "").strip()
        digest = self._extract_digest(ref)
        manifests = [self.list_by_date(date)] if date else self.list_manifests()
        for manifest in manifests:
            for asset in manifest.get("assets", []):
                if digest and asset.get("sha256") == digest:
                    return asset
                if ref and ref in {asset.get("url"), asset.get("path"), asset.get("sha256")}:
                    return asset
                if original_name and asset.get("original_name") == original_name:
                    return asset
        if digest:
            blob = self.find_blob(digest)
            if blob:
                asset = {
                    "sha256": digest,
                    "path": str(blob),
                    "url": f"/media/blobs/{digest}",
                    "original_name": blob.name,
                    "date": date,
                }
                asset.update(self._file_metadata(blob))
                return asset
        return None

    def storage_summary(self) -> dict:
        root = self.paths.media_dir / "blobs" / "sha256"
        total = 0
        count = 0
        if root.exists():
            for path in root.glob("*/*/*"):
                if path.is_file():
                    total += path.stat().st_size
                    count += 1
        return {"bytes": total, "count": count, "label": self._format_bytes(total)}

    def _with_output_metadata(self, asset: dict, date: str) -> dict:
        output = dict(asset)
        output.setdefault("date", date)
        blob = self.find_blob(output.get("sha256", ""))
        if blob:
            output["path"] = str(blob)
            output.update({key: value for key, value in self._file_metadata(blob).items() if output.get(key) in ("", None, 0)})
        output.setdefault("note", "")
        output.setdefault("url", f"/media/blobs/{output.get('sha256', '')}")
        return output

    def _file_metadata(self, path: Path) -> dict:
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        width = 0
        height = 0
        if Image is not None and mime_type.startswith("image/"):
            try:
                with Image.open(path) as image:
                    width, height = image.size
                    if image.get_format_mimetype():
                        mime_type = image.get_format_mimetype()
            except Exception:
                width = 0
                height = 0
        orientation = "landscape" if width >= height and width and height else "portrait" if width and height else "file"
        return {
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "mime_type": mime_type,
            "width": width,
            "height": height,
            "orientation": orientation,
            "is_image": mime_type.startswith("image/"),
        }

    def _extract_digest(self, value: str) -> str:
        for part in value.replace("\\", "/").split("/"):
            candidate = part.split(".")[0]
            if len(candidate) == 64 and all(char in "0123456789abcdefABCDEF" for char in candidate):
                return candidate.lower()
        if len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value):
            return value.lower()
        return ""

    def _different_paths(self, left: Path, right: Path) -> bool:
        try:
            return left.resolve() != right.resolve()
        except Exception:
            return str(left) != str(right)

    def _format_bytes(self, value: int) -> str:
        size = float(value)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024
        return f"{value} B"
