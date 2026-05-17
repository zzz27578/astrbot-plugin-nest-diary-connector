from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from nest_diary_web.paths import NestPaths


class MediaService:
    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.paths.ensure_all()

    def save_media(self, source_path: Path, date: str, original_name: str | None = None) -> dict:
        source = Path(source_path)
        digest = self._sha256(source)
        suffix = source.suffix.lower()
        blob_path = self._blob_path(digest, suffix)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        if not blob_path.exists():
            shutil.copy2(source, blob_path)

        manifest_path = self._manifest_path(date)
        manifest = self._read_manifest(manifest_path, date)
        record = {
            "sha256": digest,
            "path": str(blob_path),
            "url": f"/media/blobs/{digest}",
            "original_name": original_name or source.name,
        }
        if not any(item["sha256"] == digest for item in manifest["assets"]):
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
                manifests.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return manifests

    def list_by_date(self, date: str) -> dict:
        return self._read_manifest(self._manifest_path(date), date)

    def find_blob(self, digest: str) -> Path | None:
        root = self.paths.media_dir / "blobs" / "sha256" / digest[:2] / digest[2:4]
        if not root.exists():
            return None
        matches = list(root.glob(f"{digest}.*"))
        return matches[0] if matches else None
