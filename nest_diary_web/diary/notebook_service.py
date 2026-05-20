from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from nest_diary_web.paths import NestPaths, safe_package_id


@dataclass
class DiaryNotebook:
    id: str
    name: str
    origin_umo: str = ""
    platform_id: str = ""
    message_type: str = ""
    session_id: str = ""
    enabled: bool = True
    auto_archive_enabled: bool = True
    archive_time: str = "03:00"
    push_enabled: bool = False
    push_target: str = "none"
    push_format: str = "text"
    admins: list[str] | None = None
    created_at: str = ""
    updated_at: str = ""


class NotebookService:
    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.paths.ensure_all()
        self.path = self.paths.diary_notebook_registry_file

    def list_notebooks(self) -> list[DiaryNotebook]:
        items = self._load()
        if "default" not in items:
            items["default"] = self._default_notebook()
            self._save(items)
        return sorted(items.values(), key=lambda item: (item.id != "default", item.name, item.id))

    def get(self, notebook_id: str = "default") -> DiaryNotebook:
        notebook_id = safe_package_id(notebook_id)
        items = self._load()
        if notebook_id not in items:
            if notebook_id == "default":
                items[notebook_id] = self._default_notebook()
                self._save(items)
            else:
                raise KeyError(notebook_id)
        return items[notebook_id]

    def ensure(
        self,
        notebook_id: str = "default",
        name: str = "",
        origin_umo: str = "",
        message_type: str = "",
        platform_id: str = "",
        session_id: str = "",
    ) -> DiaryNotebook:
        notebook_id = safe_package_id(notebook_id)
        items = self._load()
        now = self._now()
        current = items.get(notebook_id)
        if current is None:
            current = DiaryNotebook(
                id=notebook_id,
                name=name or self._name_from_origin(origin_umo, notebook_id),
                origin_umo=origin_umo,
                platform_id=platform_id,
                message_type=message_type,
                session_id=session_id,
                admins=[],
                created_at=now,
                updated_at=now,
            )
        else:
            if name:
                current.name = name
            if origin_umo:
                current.origin_umo = origin_umo
            if platform_id:
                current.platform_id = platform_id
            if message_type:
                current.message_type = message_type
            if session_id:
                current.session_id = session_id
            current.updated_at = now
        items[notebook_id] = current
        self._save(items)
        return current

    def save_notebooks(self, notebooks: list[dict], delete_ids: list[str] | None = None) -> list[DiaryNotebook]:
        items = self._load()
        now = self._now()
        for raw_id in delete_ids or []:
            notebook_id = safe_package_id(str(raw_id or ""))
            if not notebook_id or notebook_id == "default":
                continue
            items.pop(notebook_id, None)
            notebook_dir = self.paths.diary_notebooks_dir / notebook_id
            if notebook_dir.exists():
                shutil.rmtree(notebook_dir)
        for raw in notebooks:
            raw_id = str(raw.get("id") or raw.get("notebook_id") or "").strip()
            if not raw_id:
                continue
            notebook_id = safe_package_id(raw_id)
            if not notebook_id:
                continue
            current = items.get(notebook_id) or DiaryNotebook(
                id=notebook_id,
                name=str(raw.get("name") or notebook_id),
                created_at=now,
                updated_at=now,
                admins=[],
            )
            current.name = str(raw.get("name") or current.name or notebook_id).strip() or notebook_id
            current.origin_umo = str(raw.get("origin_umo", current.origin_umo or "") or "").strip()
            if current.origin_umo and (not raw.get("platform_id") or not raw.get("message_type") or not raw.get("session_id")):
                parts = current.origin_umo.split(":", 2)
                if len(parts) == 3:
                    current.platform_id = parts[0]
                    current.message_type = parts[1]
                    current.session_id = parts[2]
            current.platform_id = str(raw.get("platform_id", current.platform_id or "") or "").strip()
            current.message_type = str(raw.get("message_type", current.message_type or "") or "").strip()
            current.session_id = str(raw.get("session_id", current.session_id or "") or "").strip()
            current.enabled = bool(raw.get("enabled", current.enabled))
            current.auto_archive_enabled = bool(raw.get("auto_archive_enabled", current.auto_archive_enabled))
            current.archive_time = str(raw.get("archive_time") or current.archive_time or "03:00").strip()
            current.push_enabled = bool(raw.get("push_enabled", current.push_enabled))
            current.push_target = str(raw.get("push_target") or current.push_target or "none").strip()
            if current.push_target not in {"none", "source", "admin_private", "both"}:
                current.push_target = "none"
            current.push_format = str(raw.get("push_format") or current.push_format or "text").strip()
            admins = raw.get("admins")
            if isinstance(admins, list):
                current.admins = [str(item).strip() for item in admins if str(item).strip()]
            current.updated_at = now
            items[notebook_id] = current
        if "default" not in items:
            items["default"] = self._default_notebook()
        self._save(items)
        return self.list_notebooks()

    def resolve_from_origin(self, origin_umo: str, default: str = "default") -> DiaryNotebook:
        if not origin_umo:
            return self.get(default)
        items = self._load()
        for item in items.values():
            if item.origin_umo == origin_umo:
                return item
        parts = origin_umo.split(":", 2)
        platform_id = parts[0] if len(parts) > 0 else ""
        message_type = parts[1] if len(parts) > 1 else ""
        session_id = parts[2] if len(parts) > 2 else ""
        prefix = "group" if message_type == "group" else "private" if message_type == "private" else "session"
        notebook_id = safe_package_id(f"{prefix}_{platform_id}_{session_id}")
        return self.ensure(
            notebook_id=notebook_id,
            origin_umo=origin_umo,
            platform_id=platform_id,
            message_type=message_type,
            session_id=session_id,
        )

    def _default_notebook(self) -> DiaryNotebook:
        now = self._now()
        return DiaryNotebook(id="default", name="默认日记本", admins=[], created_at=now, updated_at=now)

    def _load(self) -> dict[str, DiaryNotebook]:
        if not self.path.exists():
            return {"default": self._default_notebook()}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        raw_items = data.get("items", data if isinstance(data, dict) else [])
        items: dict[str, DiaryNotebook] = {}
        iterable = raw_items.values() if isinstance(raw_items, dict) else raw_items
        for raw in iterable:
            if not isinstance(raw, dict):
                continue
            notebook_id = safe_package_id(str(raw.get("id") or ""))
            if not notebook_id:
                continue
            values = asdict(self._default_notebook())
            values.update(raw)
            values["id"] = notebook_id
            values["admins"] = values.get("admins") or []
            items[notebook_id] = DiaryNotebook(**values)
        return items

    def _save(self, items: dict[str, DiaryNotebook]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": [asdict(item) for item in sorted(items.values(), key=lambda item: item.id)]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _name_from_origin(self, origin_umo: str, fallback: str) -> str:
        if not origin_umo:
            return fallback
        parts = origin_umo.split(":", 2)
        if len(parts) == 3:
            label = "群组" if parts[1] == "group" else "私聊" if parts[1] == "private" else "会话"
            return f"{label} {parts[2]}"
        return fallback

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
