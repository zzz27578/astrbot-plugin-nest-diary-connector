"""模块隔离存储。

轻量模块（只有 module.json + page.js）靠这一层落地数据，不需要自带后端。
每个模块只能读写自己的 ``modules/<module-id>/data/store/`` 目录，键名与体积都受限。
"""

from __future__ import annotations

import json
from pathlib import Path

from .module_registry import STORE_MAX_BYTES, STORE_MAX_KEYS
from .paths import NestPaths, safe_package_id


class ModuleStoreError(Exception):
    """存储层可预期的拒绝原因，由路由层翻成 4xx。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ModuleStore:
    def __init__(self, paths: NestPaths) -> None:
        self.paths = paths

    def _store_dir(self, module_id: str) -> Path:
        safe_module = safe_package_id(module_id, "")
        if not safe_module or safe_module != module_id:
            raise ModuleStoreError("模块 ID 不合法。", 400)
        return self.paths.modules_dir / safe_module / "data" / "store"

    @staticmethod
    def _safe_key(key: str) -> str:
        safe = safe_package_id(key, "")
        if not safe or safe != key.strip():
            raise ModuleStoreError("存储键只能包含字母、数字、下划线、点和连字符。", 400)
        if len(safe) > 64:
            raise ModuleStoreError("存储键过长，最多 64 个字符。", 400)
        return safe

    def list_keys(self, module_id: str) -> list[dict]:
        store_dir = self._store_dir(module_id)
        if not store_dir.is_dir():
            return []
        items: list[dict] = []
        for path in sorted(store_dir.glob("*.json")):
            try:
                size = path.stat().st_size
            except OSError:
                continue
            items.append({"key": path.stem, "bytes": size})
        return items

    def read(self, module_id: str, key: str) -> dict:
        path = self._store_dir(module_id) / f"{self._safe_key(key)}.json"
        if not path.is_file():
            return {"key": key, "value": None, "exists": False}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModuleStoreError(f"存储文件读取失败：{exc}", 500) from exc
        return {"key": key, "value": value, "exists": True}

    def write(self, module_id: str, key: str, value: object, max_bytes: int = STORE_MAX_BYTES) -> dict:
        store_dir = self._store_dir(module_id)
        safe_key = self._safe_key(key)
        try:
            payload = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ModuleStoreError(f"值必须可序列化为 JSON：{exc}", 400) from exc

        encoded = payload.encode("utf-8")
        limit = max(1024, min(STORE_MAX_BYTES, int(max_bytes or STORE_MAX_BYTES)))
        if len(encoded) > limit:
            raise ModuleStoreError(f"单个存储文档不能超过 {limit} 字节，当前 {len(encoded)} 字节。", 413)

        target = store_dir / f"{safe_key}.json"
        if not target.exists() and len(self.list_keys(module_id)) >= STORE_MAX_KEYS:
            raise ModuleStoreError(f"单个模块最多 {STORE_MAX_KEYS} 个存储键。", 409)

        store_dir.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(target)
        return {"key": safe_key, "bytes": len(encoded), "exists": True}

    def delete(self, module_id: str, key: str) -> dict:
        path = self._store_dir(module_id) / f"{self._safe_key(key)}.json"
        existed = path.is_file()
        if existed:
            path.unlink()
        return {"key": key, "deleted": existed}
