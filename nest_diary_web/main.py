from __future__ import annotations

import json
import mimetypes
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.requests import Request

from .auth import verify_bearer_token_from_store
from .backup_service import BackupService
from .config import load_settings
from .diary.diary_service import DiaryService
from .memory.impression_service import ImpressionService
from .media.media_service import MediaService
from .models import DiaryEntry, PersonImpression, ServiceUiSettings
from .paths import NestPaths
from .settings_service import SecuritySettingsStore, ServiceSettingsStore
from .version_service import VersionService
from .web.routes import create_web_router, mount_static
from .web_auth import WebSessionAuth

APP_VERSION = "0.5.7"
settings = load_settings()
app = FastAPI(title="Nest Service", version=APP_VERSION)
WEB_DIST_DIR = Path(__file__).resolve().parent / "web_dist"
BUILTIN_APPEARANCE_ROOT = WEB_DIST_DIR / "appearance"
AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
paths = NestPaths(settings.data_dir)
diary_service = DiaryService(paths)
media_service = MediaService(paths)
impression_service = ImpressionService(paths)
service_settings = ServiceSettingsStore(paths)
backup_service = BackupService(paths)
version_service = VersionService(
    current_version=APP_VERSION,
    repo_root=Path(__file__).resolve().parents[1],
    enable_self_update=settings.enable_self_update,
)
security_settings = SecuritySettingsStore(
    paths,
    default_admin_password=settings.admin_password or "12345678",
    default_bot_api_token=settings.bot_api_token,
)
initial_security = security_settings.load()
web_auth = WebSessionAuth(
    admin_password=initial_security.admin_password,
    session_secret=initial_security.bot_api_token or "development-session-secret",
)
if (WEB_DIST_DIR / "assets").exists():
    app.mount("/app-assets", StaticFiles(directory=str(WEB_DIST_DIR / "assets")), name="app-assets")
mount_static(app)


def require_web_session(request: Request) -> None:
    if not web_auth.verify_session(request.cookies.get("nest_session")):
        raise HTTPException(status_code=401, detail="Web session required")


def spa_index(request: Request):
    if not web_auth.verify_session(request.cookies.get("nest_session")):
        return RedirectResponse("/login", status_code=303)
    index_path = WEB_DIST_DIR / "index.html"
    if not index_path.exists():
        return RedirectResponse("/diary", status_code=303)
    return FileResponse(index_path)


def spa_index_date(date: str, request: Request):
    return spa_index(request)


for spa_route in [
    "/",
    "/dashboard",
    "/diary",
    "/write",
    "/search",
    "/impressions",
    "/media",
    "/settings",
]:
    app.add_api_route(spa_route, spa_index, methods=["GET"], include_in_schema=False)
app.add_api_route("/diary/{date}", spa_index_date, methods=["GET"], include_in_schema=False)

app.include_router(
    create_web_router(
        web_auth,
        diary_service,
        media_service,
        diary_service.revisions,
        impression_service,
        service_settings,
        security_settings,
        web_auth,
        version_service,
        backup_service,
        settings,
    )
)


def _entry_payload(entry: DiaryEntry) -> dict:
    return {
        "id": f"{entry.notebook_id}:{entry.date}",
        "date": entry.date,
        "notebook_id": entry.notebook_id,
        "notebook_name": entry.notebook_name,
        "origin_umo": entry.origin_umo,
        "platform_id": entry.platform_id,
        "message_type": entry.message_type,
        "session_id": entry.session_id,
        "title": entry.normalized_title(),
        "mood": entry.mood,
        "tags": entry.tags,
        "people": entry.people,
        "media_refs": entry.media_refs,
        "importance": entry.importance,
        "source": entry.source,
        "revision": entry.revision,
        "body": entry.body,
    }


def _settings_payload() -> dict:
    return asdict(service_settings.load())


def _security_payload() -> dict:
    security = security_settings.load()
    return {
        "bot_api_token": security.bot_api_token,
        "external_api_enabled": security.external_api_enabled,
        "admin_password_set": bool(security.admin_password),
    }


def _custom_webui_root(ui_settings: ServiceUiSettings | None = None) -> Path:
    loaded = ui_settings or service_settings.load()
    configured = loaded.custom_webui_dir.strip()
    if configured:
        return Path(configured).expanduser()
    return paths.user_custom_dir / "webui"


def _frontend_styles(ui_settings: ServiceUiSettings) -> list[dict]:
    styles = [{"id": "default", "name": "官方默认", "kind": "official"}]
    themes_dir = _custom_webui_root(ui_settings) / "themes"
    if themes_dir.exists():
        for path in sorted(themes_dir.iterdir()):
            if path.is_dir():
                styles.append({"id": path.name, "name": path.name, "kind": "custom"})
    if ui_settings.active_frontend_style not in {item["id"] for item in styles}:
        styles.append({"id": ui_settings.active_frontend_style, "name": ui_settings.active_frontend_style, "kind": "missing"})
    return styles


def _module_catalog(ui_settings: ServiceUiSettings) -> dict:
    official = _discover_official_modules()
    custom = _discover_custom_packages(ui_settings, "modules", "module")
    extensions = _discover_custom_packages(ui_settings, "extensions", "extension")
    appearance = _discover_appearance_modules(ui_settings)
    return {
        "official": official,
        "custom": custom,
        "extensions": extensions,
        "appearance": appearance,
        "conflicts": _module_conflicts(ui_settings, official, custom, extensions),
        "appearance_conflicts": _appearance_conflicts(ui_settings, appearance),
    }


def _discover_official_modules() -> list[dict]:
    modules_root = Path(__file__).resolve().parents[1] / "modules"
    modules: list[dict] = []
    for module_id in ["diary", "impressions", "media", "webui"]:
        item = _load_package_manifest(
            modules_root / module_id / "module.json",
            {
                "id": module_id,
                "name": module_id,
                "type": "module",
                "description": "",
                "feature_tags": [f"{module_id}-core"],
                "replaces": [],
                "conflicts_with": [],
                "ui_category": "appearance" if module_id == "webui" else "core",
            },
            kind="official",
        )
        item["ui_category"] = item.get("ui_category") or ("appearance" if module_id == "webui" else "core")
        modules.append(item)
    return modules


def _discover_custom_packages(ui_settings: ServiceUiSettings, folder_name: str, package_type: str) -> list[dict]:
    packages: dict[str, dict] = {}
    if package_type == "module":
        module_paths = sorted(paths.modules_dir.iterdir()) if paths.modules_dir.exists() else []
        for path in module_paths:
            if path.is_dir() and path.name not in {"diary", "impressions", "media", "extensions", "archive"}:
                packages[path.name] = _load_package_manifest(
                    path / "module.json",
                    {
                        "id": path.name,
                        "name": path.name,
                        "type": "module",
                        "description": "",
                        "feature_tags": [],
                        "replaces": [],
                        "conflicts_with": [],
                    },
                    kind="custom",
                    data_path=str(path),
                )
    else:
        extension_root = paths.modules_dir / "extensions"
        if extension_root.exists():
            for path in sorted(extension_root.iterdir()):
                if path.is_dir():
                    packages[path.name] = _load_package_manifest(
                        path / "module.json",
                        {
                            "id": path.name,
                            "name": path.name,
                            "type": "extension",
                            "description": "",
                            "feature_tags": [],
                            "target_modules": [],
                            "conflicts_with": [],
                        },
                        kind="extension",
                        data_path=str(path),
                    )

    frontend_root = _custom_webui_root(ui_settings) / folder_name
    if frontend_root.exists():
        for path in sorted(frontend_root.iterdir()):
            if not path.is_dir():
                continue
            current = packages.get(path.name)
            loaded = _load_package_manifest(
                path / "module.json",
                {
                    "id": path.name,
                    "name": path.name,
                    "type": package_type,
                    "description": "",
                    "feature_tags": [],
                    "conflicts_with": [],
                },
                kind="extension" if package_type == "extension" else "custom",
                frontend_path=str(path),
            )
            if current:
                current["frontend_path"] = str(path)
                for key in ["name", "description", "feature_tags", "target_modules", "replaces", "conflicts_with"]:
                    if loaded.get(key):
                        current[key] = loaded[key]
            else:
                packages[path.name] = loaded
    return sorted(packages.values(), key=lambda item: item["id"])


def _discover_appearance_modules(ui_settings: ServiceUiSettings) -> list[dict]:
    packages: dict[str, dict] = {
        "nest-tactical": _load_package_manifest(
            BUILTIN_APPEARANCE_ROOT / "nest-tactical" / "module.json",
            {
                "id": "nest-tactical",
                "name": "小窝战术终端",
                "type": "appearance",
                "description": "官方全局外观模块。以清晰信息层级、工业控制台质感和轻量动效重塑小窝页面。",
                "feature_tags": ["webui-appearance", "official-global-appearance"],
                "appearance_scope": "global",
                "appearance_mode": "global",
                "conflicts_with": [],
            },
            kind="official",
            frontend_path=str(BUILTIN_APPEARANCE_ROOT / "nest-tactical"),
        )
    }
    frontend_root = _custom_webui_root(ui_settings)
    for folder_name, default_mode in [("themes", "global"), ("appearance", "global"), ("skins", "global")]:
        root = frontend_root / folder_name
        if not root.exists():
            continue
        for path in sorted(root.iterdir()):
            if not path.is_dir():
                continue
            loaded = _load_package_manifest(
                path / "module.json",
                {
                    "id": path.name,
                    "name": path.name,
                    "type": "appearance",
                    "description": "替换小窝全局前端外观。",
                    "feature_tags": ["webui-appearance"],
                    "appearance_scope": default_mode,
                    "appearance_mode": "global",
                    "conflicts_with": [],
                },
                kind="appearance",
                frontend_path=str(path),
            )
            loaded["appearance_scope"] = str(loaded.get("appearance_scope") or default_mode)
            loaded["appearance_mode"] = str(loaded.get("appearance_mode") or "global")
            loaded["entry_label"] = "全局模块" if loaded["appearance_mode"] == "global" else "补充拓展"
            packages[path.name] = loaded
    for item in packages.values():
        item["appearance_scope"] = str(item.get("appearance_scope") or "global")
        item["appearance_mode"] = str(item.get("appearance_mode") or "global")
        item["entry_label"] = "全局模块" if item["appearance_mode"] == "global" else "补充拓展"
    return sorted(packages.values(), key=lambda item: item["id"])


def _load_package_manifest(path: Path, fallback: dict, kind: str, data_path: str = "", frontend_path: str = "") -> dict:
    data = dict(fallback)
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            data.update(loaded)
        except Exception:
            data["manifest_error"] = "module.json 读取失败"
    data["id"] = str(data.get("id") or path.parent.name)
    data["name"] = str(data.get("name") or data["id"])
    data["type"] = str(data.get("type") or fallback.get("type") or "module")
    data["kind"] = kind
    data["description"] = str(data.get("description") or "")
    for key in ["feature_tags", "target_modules", "replaces", "conflicts_with", "tools", "web_routes", "data_roots"]:
        if not isinstance(data.get(key), list):
            data[key] = []
    if data_path:
        data["data_path"] = data_path
    if frontend_path:
        data["frontend_path"] = frontend_path
    return data


def _appearance_conflicts(ui_settings: ServiceUiSettings, appearance: list[dict]) -> list[dict]:
    enabled = [item for item in appearance if item["id"] in ui_settings.enabled_appearance_modules]
    global_enabled = [item for item in enabled if item.get("appearance_mode") == "global"]
    if ui_settings.active_frontend_style != "default" and ui_settings.active_frontend_style not in ui_settings.enabled_appearance_modules:
        active_style = next((item for item in appearance if item["id"] == ui_settings.active_frontend_style), None)
        global_enabled.append(
            active_style
            or {
                "id": ui_settings.active_frontend_style,
                "name": f"当前样式 {ui_settings.active_frontend_style}",
                "appearance_mode": "global",
            }
        )
    if len(global_enabled) <= 1:
        return []
    return [
        {
            "level": "danger",
            "title": "全局外观冲突",
            "message": "、".join(item["name"] for item in global_enabled)
            + " 都会替换小窝全局前端。建议只开启其中一个；若坚持同时启用，样式、入口或脚本可能互相覆盖。",
            "packages": [item["id"] for item in global_enabled],
        }
    ]


def _module_conflicts(ui_settings: ServiceUiSettings, official: list[dict], custom: list[dict], extensions: list[dict]) -> list[dict]:
    enabled_official = [item for item in official if item["id"] in ui_settings.enabled_official_modules]
    enabled_custom = [item for item in custom if item["id"] in ui_settings.enabled_custom_modules]
    enabled_extensions = [item for item in extensions if item["id"] in ui_settings.enabled_custom_extensions]
    enabled: list[dict] = [*enabled_official, *enabled_custom, *enabled_extensions]

    warnings: list[dict] = []
    by_id = {item["id"]: item for item in enabled}
    by_tag: dict[str, list[str]] = {}
    for item in enabled:
        if item not in enabled_extensions:
            for tag in item.get("feature_tags", []):
                by_tag.setdefault(tag, []).append(item["id"])
        for replaced in item.get("replaces", []):
            if replaced in by_id:
                warnings.append(
                    {
                        "level": "warning",
                        "title": "替代关系",
                        "message": f"{item['name']} 声明替代 {by_id[replaced]['name']}，建议只启用其中一个。",
                        "packages": [item["id"], replaced],
                    }
                )
        for target in item.get("conflicts_with", []):
            if target in by_id:
                warnings.append(
                    {
                        "level": "danger",
                        "title": "显式冲突",
                        "message": f"{item['name']} 与 {by_id[target]['name']} 声明冲突，建议禁用一个。",
                        "packages": [item["id"], target],
                    }
                )
    for tag, package_ids in by_tag.items():
        if len(package_ids) > 1:
            names = "、".join(by_id[item_id]["name"] for item_id in package_ids)
            warnings.append(
                {
                    "level": "warning",
                    "title": "功能标签重叠",
                    "message": f"{names} 都提供 `{tag}`。可以同时启用，但可能出现入口重复或数据口径不一致。",
                    "packages": package_ids,
                }
            )
    replacement_modules = [item for item in enabled_custom if item.get("replaces") or item.get("conflicts_with")]
    if len(replacement_modules) > 1:
        warnings.append(
            {
                "level": "danger",
                "title": "完整替换模块过多",
                "message": "、".join(item["name"] for item in replacement_modules)
                + " 都声明会替换或冲突于现有能力。建议一次只启用一个完整替换模块；若坚持同时启用，可能出现入口、数据口径或工具行为冲突。",
                "packages": [item["id"] for item in replacement_modules],
            }
        )
    return warnings


class DiaryWriteRequest(BaseModel):
    date: str
    body: str
    title: str | None = None
    notebook_id: str = "default"
    notebook_name: str = ""
    origin_umo: str = ""
    platform_id: str = ""
    message_type: str = ""
    session_id: str = ""
    mood: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    media_refs: list[str] = Field(default_factory=list)
    importance: int = 3
    source: str = "bot"
    reason: str = ""
    intent: str = "write_diary"
    idempotency_key: str | None = None


def require_bot_token(authorization: str | None = Header(default=None)) -> None:
    verify_bearer_token_from_store(
        lambda: ((loaded := security_settings.load()).bot_api_token, loaded.external_api_enabled),
        authorization,
    )


def require_diary_module_enabled() -> None:
    if not service_settings.load().enable_diary_module:
        raise HTTPException(status_code=403, detail="Diary module is disabled")


def require_impressions_module_enabled() -> None:
    if not service_settings.load().enable_impressions_module:
        raise HTTPException(status_code=403, detail="Impressions module is disabled")


def require_media_module_enabled() -> None:
    if not service_settings.load().enable_media_module:
        raise HTTPException(status_code=403, detail="Media module is disabled")


def _touch_impressions_from_diary(entry: DiaryEntry) -> list[PersonImpression]:
    ui_settings = service_settings.load()
    if not ui_settings.enable_impressions_module or not ui_settings.auto_impression_from_diary:
        return []
    if ui_settings.impression_write_level == "off" or ui_settings.impression_update_strategy == "manual":
        return []
    return impression_service.touch_from_diary(
        entry,
        allow_new_people=ui_settings.impression_allow_new_people
        or ui_settings.impression_update_strategy == "aggressive",
        update_existing=ui_settings.impression_update_strategy in {"evidence_only", "existing_only", "aggressive"},
        min_confidence=ui_settings.impression_min_confidence,
    )


@app.get("/api/v1/status")
async def status(_auth: None = Depends(require_bot_token)):
    return {
        "status": "ok",
        "service": "nest",
        "version": APP_VERSION,
        "data_dir": str(settings.data_dir),
        "framework_dir": str(paths.framework_dir),
        "modules_dir": str(paths.modules_dir),
    }


@app.post("/api/v1/diary/write")
async def write_diary(
    payload: DiaryWriteRequest,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    ui_settings = service_settings.load()
    media_refs = payload.media_refs if ui_settings.enable_media_module and ui_settings.allow_media_refs else []
    entry = DiaryEntry(
        date=payload.date,
        notebook_id=payload.notebook_id,
        notebook_name=payload.notebook_name,
        origin_umo=payload.origin_umo,
        platform_id=payload.platform_id,
        message_type=payload.message_type,
        session_id=payload.session_id,
        title=payload.title,
        body=payload.body,
        mood=payload.mood,
        tags=payload.tags,
        people=payload.people,
        media_refs=media_refs,
        importance=payload.importance,
        source=payload.source,
    )
    saved = diary_service.write_diary(entry, reason=payload.reason)
    touched = _touch_impressions_from_diary(saved)
    return {
        "status": "ok",
        "date": saved.date,
        "notebook_id": saved.notebook_id,
        "notebook_name": saved.notebook_name,
        "title": saved.normalized_title(),
        "impressions_touched": [item.name for item in touched],
    }


@app.get("/api/v1/diary/search")
async def search_diary(
    q: str,
    top_k: int = 8,
    snippet_chars: int = 180,
    notebook_id: str = "",
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    return {
        "query": q,
        "results": diary_service.search(q, top_k=top_k, snippet_chars=snippet_chars, notebook_id=notebook_id or None),
        "search": diary_service.search_status(),
    }


@app.get("/api/v1/diary/archive")
async def diary_archive(
    notebook_id: str = "",
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    return {"items": diary_service.archive_tree(notebook_id=notebook_id or None)}


@app.get("/api/v1/diary/notebooks")
async def diary_notebooks(
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    return {"items": diary_service.list_notebooks()}


@app.get("/api/v1/diary/{date}")
async def read_diary(
    date: str,
    notebook_id: str = "default",
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    try:
        entry = diary_service.read_by_date(date, notebook_id=notebook_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Diary entry not found") from None
    return {
        "date": entry.date,
        "notebook_id": entry.notebook_id,
        "notebook_name": entry.notebook_name,
        "origin_umo": entry.origin_umo,
        "platform_id": entry.platform_id,
        "message_type": entry.message_type,
        "session_id": entry.session_id,
        "title": entry.normalized_title(),
        "mood": entry.mood,
        "tags": entry.tags,
        "people": entry.people,
        "media_refs": entry.media_refs,
        "importance": entry.importance,
        "source": entry.source,
        "revision": entry.revision,
        "body": entry.body,
    }


class MediaAttachRequest(BaseModel):
    source_path: str
    date: str
    original_name: str | None = None
    note: str = ""
    actor_is_admin: bool = False
    autonomous: bool = True


class MediaResolveRequest(BaseModel):
    media_ref: str = ""
    date: str = ""
    original_name: str = ""


class MediaFolderCreateRequest(BaseModel):
    name: str = ""
    tags: list[str] = Field(default_factory=list)
    note: str = ""


class MediaFolderUpdateRequest(BaseModel):
    folder_id: str
    name: str = ""
    tags: list[str] = Field(default_factory=list)
    note: str = ""


class MediaMoveRequest(BaseModel):
    sha256: str
    folder_id: str = ""


class MediaTrashRequest(BaseModel):
    item_type: str
    item_id: str


class MediaNoteUpdateRequest(BaseModel):
    sha256: str
    note: str = ""


@app.post("/api/v1/media/attach")
async def attach_media(
    payload: MediaAttachRequest,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_media_module_enabled),
):
    ui_settings = service_settings.load()
    if ui_settings.media_auto_save_policy == "admin_only" and not payload.actor_is_admin:
        raise HTTPException(status_code=403, detail="Only the small-nest administrator can save media")
    if ui_settings.media_auto_save_policy == "admin_allowed" and not payload.actor_is_admin:
        raise HTTPException(status_code=403, detail="Only the small-nest administrator can save media")
    if payload.autonomous and not ui_settings.media_allow_bot_import:
        raise HTTPException(status_code=403, detail="Bot media import is disabled")
    if ui_settings.media_auto_save_limit_12h and media_service.count_saved_since(12) >= ui_settings.media_auto_save_limit_12h:
        raise HTTPException(status_code=400, detail="Media 12-hour limit reached")
    if len(media_service.list_by_date(payload.date).get("assets", [])) >= ui_settings.media_max_items_per_day:
        raise HTTPException(status_code=400, detail="Media limit reached for this date")
    source = Path(payload.source_path)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Media source file not found")
    record = media_service.save_media(
        source,
        date=payload.date,
        original_name=payload.original_name,
        note=payload.note,
        storage_strategy=ui_settings.media_storage_strategy,
    )
    return {"status": "ok", "asset": record}


@app.post("/api/v1/media/resolve")
async def resolve_media(
    payload: MediaResolveRequest,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_media_module_enabled),
):
    asset = media_service.find_asset(
        media_ref=payload.media_ref,
        date=payload.date,
        original_name=payload.original_name,
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return {"status": "ok", "asset": asset}


@app.get("/api/v1/media/by-date/{date}")
async def list_media_by_date(
    date: str,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_media_module_enabled),
):
    return media_service.list_by_date(date)


@app.get("/media/blobs/{digest}")
async def read_media_blob(digest: str):
    blob = media_service.find_blob(digest)
    if not blob:
        raise HTTPException(status_code=404, detail="Media blob not found")
    media_type = mimetypes.guess_type(blob.name)[0] or "application/octet-stream"
    return FileResponse(blob, media_type=media_type)


class ImpressionWriteRequest(BaseModel):
    previous_name: str = ""
    name: str
    summary: str
    identity: str = ""
    traits: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    relationship: str = ""
    affinity: int = 3
    special_comment: str = ""
    evidence_dates: list[str] = Field(default_factory=list)
    confidence: int = 3
    notes: str = ""


class SettingsUpdateRequest(BaseModel):
    site_title: str = "小窝"
    site_subtitle: str = "把今天安放好，旧事也能被轻轻找回来"
    brand_avatar_url: str = ""
    search_default_top_k: int = 5
    search_snippet_chars: int = 180
    memory_recall_enabled: bool = True
    memory_recall_policy: str = "conservative"
    enable_diary_module: bool = True
    diary_archive_granularity: str = "day"
    diary_display_mode: str = "grouped"
    admin_private_diary_enabled: bool = False
    admin_private_push_enabled: bool = False
    diary_push_format: str = "text"
    diary_push_target: str = "none"
    diary_t2i_template_name: str = "plain_note"
    permissions_allow_admin_natural_language: bool = True
    non_admin_permissions: list[str] = Field(default_factory=list)
    nest_admin_ids: str = ""
    diary_write_prompt: str = ""
    diary_t2i_template: str = ""
    enable_media_module: bool = True
    allow_media_refs: bool = True
    media_max_items_per_day: int = 80
    media_auto_save_policy: str = "admin_only"
    media_auto_save_limit_12h: int = 10
    media_auto_album_strategy: str = "confirm"
    media_allow_bot_import: bool = True
    media_auto_album: bool = True
    media_storage_strategy: str = "copy"
    enable_impressions_module: bool = True
    auto_impression_from_diary: bool = False
    impression_write_level: str = "balanced"
    impression_update_strategy: str = "evidence_only"
    impression_allow_new_people: bool = False
    impression_min_confidence: int = 3
    show_impression_prompt: bool = True
    active_frontend_style: str = "default"
    enabled_official_modules: list[str] = Field(default_factory=lambda: ["diary", "impressions", "media", "webui"])
    enabled_custom_modules: list[str] = Field(default_factory=list)
    enabled_custom_extensions: list[str] = Field(default_factory=list)
    enabled_appearance_modules: list[str] = Field(default_factory=list)
    appearance_modules_initialized: bool = True
    custom_webui_dir: str = ""
    backup_custom_before_update: bool = True
    impression_prompt: str = ""


class SecurityUpdateRequest(BaseModel):
    admin_password: str | None = None
    bot_api_token: str = ""
    generate_bot_api_token: bool = False
    external_api_enabled: bool = False


class NotebookUpdateRequest(BaseModel):
    notebooks: list[dict] = Field(default_factory=list)
    delete_ids: list[str] = Field(default_factory=list)
    replace: bool = False


@app.get("/api/v1/impressions")
async def list_impressions(
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_impressions_module_enabled),
):
    return {"items": [item.__dict__ for item in impression_service.list_people()]}


@app.get("/api/v1/impressions/{name}")
async def read_impression(
    name: str,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_impressions_module_enabled),
):
    impression = impression_service.get(name)
    if not impression:
        raise HTTPException(status_code=404, detail="Person impression not found")
    return impression.__dict__


@app.post("/api/v1/impressions/write")
async def write_impression(
    payload: ImpressionWriteRequest,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_impressions_module_enabled),
):
    previous_name = payload.previous_name.strip()
    next_name = payload.name.strip()
    if not next_name:
        raise HTTPException(status_code=400, detail="Person name is required")
    if previous_name and previous_name != next_name:
        impression_service.delete(previous_name)
    saved = impression_service.save(
        PersonImpression(
            name=next_name,
            summary=payload.summary.strip(),
            identity=payload.identity.strip(),
            traits=payload.traits,
            hobbies=payload.hobbies,
            interests=payload.interests,
            preferences=payload.preferences,
            relationship=payload.relationship.strip(),
            affinity=payload.affinity,
            special_comment=payload.special_comment.strip(),
            evidence_dates=payload.evidence_dates,
            confidence=payload.confidence,
            notes=payload.notes.strip(),
        )
    )
    return {"status": "ok", "item": saved.__dict__}


@app.delete("/api/v1/impressions/{name}")
async def delete_impression(
    name: str,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_impressions_module_enabled),
):
    if not impression_service.delete(name):
        raise HTTPException(status_code=404, detail="Person impression not found")
    return {"status": "ok"}


@app.get("/api/ui/bootstrap")
async def ui_bootstrap(_session: None = Depends(require_web_session)):
    ui_settings = service_settings.load()
    entries = diary_service.list_entries()
    media = media_service.list_manifests()
    people = impression_service.list_people()
    return {
        "version": APP_VERSION,
        "service": "nest",
        "stats": {
            "entries": len(entries),
            "media": sum(len(item.get("assets", [])) for item in media),
            "people": len(people),
        },
        "recent_entries": [_entry_payload(entry) for entry in entries[:6]],
        "archive": diary_service.archive_tree(),
        "notebooks": diary_service.list_notebooks(),
        "settings": _settings_payload(),
        "security": _security_payload(),
        "notebooks": diary_service.list_notebooks(),
        "search": diary_service.search_status(),
        "frontend_styles": _frontend_styles(ui_settings),
        "module_catalog": _module_catalog(ui_settings),
        "data_dir": str(settings.data_dir),
        "framework_dir": str(paths.framework_dir),
        "modules_dir": str(paths.modules_dir),
    }


@app.get("/api/ui/diary")
async def ui_list_diary(notebook_id: str = "", _session: None = Depends(require_web_session)):
    return {
        "items": [_entry_payload(entry) for entry in diary_service.list_entries(notebook_id=notebook_id or None)],
        "archive": diary_service.archive_tree(notebook_id=notebook_id or None),
        "notebooks": diary_service.list_notebooks(),
    }


@app.get("/api/ui/diary/{date}")
async def ui_read_diary(date: str, notebook_id: str = "default", _session: None = Depends(require_web_session)):
    try:
        return _entry_payload(diary_service.read_by_date(date, notebook_id=notebook_id))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Diary entry not found") from None


@app.post("/api/ui/diary")
async def ui_write_diary(payload: DiaryWriteRequest, _session: None = Depends(require_web_session)):
    ui_settings = service_settings.load()
    if not ui_settings.enable_diary_module:
        raise HTTPException(status_code=403, detail="Diary module is disabled")
    media_refs = payload.media_refs if ui_settings.enable_media_module and ui_settings.allow_media_refs else []
    entry = DiaryEntry(
        date=payload.date,
        notebook_id=payload.notebook_id,
        notebook_name=payload.notebook_name,
        origin_umo=payload.origin_umo,
        platform_id=payload.platform_id,
        message_type=payload.message_type,
        session_id=payload.session_id,
        title=payload.title,
        body=payload.body,
        mood=payload.mood,
        tags=payload.tags,
        people=payload.people,
        media_refs=media_refs,
        importance=payload.importance,
        source=payload.source or "admin",
    )
    saved = diary_service.write_diary(entry, reason=payload.reason or "web_app_update")
    touched = _touch_impressions_from_diary(saved)
    return {"status": "ok", "entry": _entry_payload(saved), "impressions_touched": [item.name for item in touched]}


@app.delete("/api/ui/diary/{date}")
async def ui_delete_diary(date: str, notebook_id: str = "default", _session: None = Depends(require_web_session)):
    deleted = diary_service.delete_diary(date, reason="web_app_delete", notebook_id=notebook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Diary entry not found")
    return {"status": "ok"}


@app.get("/api/ui/search")
async def ui_search(q: str = "", top_k: int = 5, notebook_id: str = "", _session: None = Depends(require_web_session)):
    ui_settings = service_settings.load()
    if not q or not ui_settings.enable_diary_module:
        return {"query": q, "results": [], "search": diary_service.search_status(), "notebooks": diary_service.list_notebooks()}
    return {
        "query": q,
        "results": diary_service.search(q, top_k=top_k or ui_settings.search_default_top_k, snippet_chars=ui_settings.search_snippet_chars, notebook_id=notebook_id or None),
        "search": diary_service.search_status(),
        "notebooks": diary_service.list_notebooks(),
    }


@app.get("/api/ui/notebooks")
async def ui_list_notebooks(_session: None = Depends(require_web_session)):
    return {"items": diary_service.list_notebooks()}


@app.post("/api/ui/notebooks")
async def ui_save_notebooks(payload: NotebookUpdateRequest, _session: None = Depends(require_web_session)):
    return {
        "status": "ok",
        "items": diary_service.save_notebooks(
            payload.notebooks,
            delete_ids=payload.delete_ids,
            replace=payload.replace,
        ),
    }


@app.get("/api/ui/impressions")
async def ui_list_impressions(_session: None = Depends(require_web_session)):
    if not service_settings.load().enable_impressions_module:
        return {"items": []}
    return {"items": [item.__dict__ for item in impression_service.list_people()]}


@app.get("/api/ui/impressions/{name}")
async def ui_read_impression(name: str, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_impressions_module:
        raise HTTPException(status_code=403, detail="Impressions module is disabled")
    impression = impression_service.get(name)
    if not impression:
        raise HTTPException(status_code=404, detail="Person impression not found")
    return impression.__dict__


@app.post("/api/ui/impressions")
async def ui_write_impression(payload: ImpressionWriteRequest, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_impressions_module:
        raise HTTPException(status_code=403, detail="Impressions module is disabled")
    previous_name = payload.previous_name.strip()
    next_name = payload.name.strip()
    if not next_name:
        raise HTTPException(status_code=400, detail="Person name is required")
    if previous_name and previous_name != next_name:
        impression_service.delete(previous_name)
    saved = impression_service.save(
        PersonImpression(
            name=next_name,
            summary=payload.summary.strip(),
            identity=payload.identity.strip(),
            traits=payload.traits,
            hobbies=payload.hobbies,
            interests=payload.interests,
            preferences=payload.preferences,
            relationship=payload.relationship.strip(),
            affinity=payload.affinity,
            special_comment=payload.special_comment.strip(),
            evidence_dates=payload.evidence_dates,
            confidence=payload.confidence,
            notes=payload.notes.strip(),
        )
    )
    return {"status": "ok", "item": saved.__dict__}


@app.delete("/api/ui/impressions/{name}")
async def ui_delete_impression(name: str, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_impressions_module:
        raise HTTPException(status_code=403, detail="Impressions module is disabled")
    if not impression_service.delete(name):
        raise HTTPException(status_code=404, detail="Person impression not found")
    return {"status": "ok"}


@app.get("/api/ui/media")
async def ui_media(_session: None = Depends(require_web_session)):
    if not service_settings.load().enable_media_module:
        return {"items": [], "storage": {"bytes": 0, "count": 0, "label": "0 B"}, "organization": media_service.load_organization()}
    return {
        "items": media_service.list_manifests(),
        "storage": media_service.storage_summary(),
        "organization": media_service.load_organization(),
    }


@app.post("/api/ui/media/folders")
async def ui_create_media_folder(payload: MediaFolderCreateRequest, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_media_module:
        raise HTTPException(status_code=403, detail="Media module is disabled")
    folder = media_service.create_folder(payload.name, tags=payload.tags, note=payload.note)
    return {"status": "ok", "folder": folder, "organization": media_service.load_organization()}


@app.post("/api/ui/media/folders/update")
async def ui_update_media_folder(payload: MediaFolderUpdateRequest, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_media_module:
        raise HTTPException(status_code=403, detail="Media module is disabled")
    try:
        folder = media_service.update_folder(payload.folder_id, payload.name, tags=payload.tags, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "folder": folder, "organization": media_service.load_organization()}


@app.post("/api/ui/media/move")
async def ui_move_media(payload: MediaMoveRequest, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_media_module:
        raise HTTPException(status_code=403, detail="Media module is disabled")
    try:
        organization = media_service.move_asset_to_folder(payload.sha256, payload.folder_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "organization": organization}


@app.post("/api/ui/media/note")
async def ui_update_media_note(payload: MediaNoteUpdateRequest, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_media_module:
        raise HTTPException(status_code=403, detail="Media module is disabled")
    try:
        asset = media_service.update_asset_note(payload.sha256, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "asset": asset}


@app.post("/api/ui/media/trash")
async def ui_trash_media(payload: MediaTrashRequest, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_media_module:
        raise HTTPException(status_code=403, detail="Media module is disabled")
    try:
        organization = media_service.trash_item(payload.item_type, payload.item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "organization": organization}


@app.post("/api/ui/media/restore")
async def ui_restore_media(payload: MediaTrashRequest, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_media_module:
        raise HTTPException(status_code=403, detail="Media module is disabled")
    organization = media_service.restore_item(payload.item_type, payload.item_id)
    return {"status": "ok", "organization": organization}


@app.post("/api/ui/media/delete")
async def ui_delete_media(payload: MediaTrashRequest, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_media_module:
        raise HTTPException(status_code=403, detail="Media module is disabled")
    try:
        organization = media_service.delete_item(payload.item_type, payload.item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "organization": organization}


@app.get("/api/ui/settings")
async def ui_get_settings(_session: None = Depends(require_web_session)):
    ui_settings = service_settings.load()
    return {
        "settings": _settings_payload(),
        "security": _security_payload(),
        "search": diary_service.search_status(),
        "notebooks": diary_service.list_notebooks(),
        "frontend_styles": _frontend_styles(ui_settings),
        "module_catalog": _module_catalog(ui_settings),
        "runtime": {
            "data_dir": str(settings.data_dir),
            "framework_dir": str(paths.framework_dir),
            "modules_dir": str(paths.modules_dir),
            "custom_webui_dir": str(_custom_webui_root(ui_settings)),
            "port": settings.port,
            "self_update": settings.enable_self_update,
        },
    }


@app.get("/api/ui/avatar")
async def ui_avatar(_session: None = Depends(require_web_session)):
    for suffix in AVATAR_EXTENSIONS:
        path = paths.framework_dir / "assets" / f"brand-avatar{suffix}"
        if path.exists():
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="Avatar not found")


@app.post("/api/ui/avatar")
async def ui_upload_avatar(file: UploadFile = File(...), _session: None = Depends(require_web_session)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in AVATAR_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only png, jpg, webp or gif avatars are supported")
    target_dir = paths.framework_dir / "assets"
    target_dir.mkdir(parents=True, exist_ok=True)
    for old_suffix in AVATAR_EXTENSIONS:
        old = target_dir / f"brand-avatar{old_suffix}"
        if old.exists():
            old.unlink()
    target = target_dir / f"brand-avatar{suffix}"
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Avatar must be 2MB or smaller")
    target.write_bytes(content)
    avatar_url = f"/api/ui/avatar?v={int(target.stat().st_mtime)}"
    current = service_settings.load()
    current.brand_avatar_url = avatar_url
    service_settings.save(current)
    return {"status": "ok", "avatar_url": avatar_url}


@app.post("/api/ui/settings")
async def ui_save_settings(payload: SettingsUpdateRequest, _session: None = Depends(require_web_session)):
    saved = service_settings.save(
        ServiceUiSettings(
            site_title=payload.site_title,
            site_subtitle=payload.site_subtitle,
            brand_avatar_url=payload.brand_avatar_url,
            search_default_top_k=payload.search_default_top_k,
            search_snippet_chars=payload.search_snippet_chars,
            memory_recall_enabled=payload.memory_recall_enabled,
            memory_recall_policy=payload.memory_recall_policy,
            enable_diary_module=payload.enable_diary_module,
            diary_archive_granularity=payload.diary_archive_granularity,
            diary_display_mode=payload.diary_display_mode,
            admin_private_diary_enabled=payload.admin_private_diary_enabled,
            admin_private_push_enabled=payload.admin_private_push_enabled,
            diary_push_format=payload.diary_push_format,
            diary_push_target=payload.diary_push_target,
            diary_t2i_template_name=payload.diary_t2i_template_name,
            permissions_allow_admin_natural_language=payload.permissions_allow_admin_natural_language,
            non_admin_permissions=payload.non_admin_permissions,
            nest_admin_ids=payload.nest_admin_ids,
            diary_write_prompt=payload.diary_write_prompt,
            diary_t2i_template=payload.diary_t2i_template,
            enable_media_module=payload.enable_media_module,
            allow_media_refs=payload.allow_media_refs,
            media_max_items_per_day=payload.media_max_items_per_day,
            media_auto_save_policy=payload.media_auto_save_policy,
            media_auto_save_limit_12h=payload.media_auto_save_limit_12h,
            media_auto_album_strategy=payload.media_auto_album_strategy,
            media_allow_bot_import=payload.media_allow_bot_import,
            media_auto_album=payload.media_auto_album,
            media_storage_strategy=payload.media_storage_strategy,
            enable_impressions_module=payload.enable_impressions_module,
            auto_impression_from_diary=payload.auto_impression_from_diary,
            impression_write_level=payload.impression_write_level,
            impression_update_strategy=payload.impression_update_strategy,
            impression_allow_new_people=payload.impression_allow_new_people,
            impression_min_confidence=payload.impression_min_confidence,
            show_impression_prompt=payload.show_impression_prompt,
            active_frontend_style=payload.active_frontend_style,
            enabled_official_modules=payload.enabled_official_modules,
            enabled_custom_modules=payload.enabled_custom_modules,
            enabled_custom_extensions=payload.enabled_custom_extensions,
            enabled_appearance_modules=payload.enabled_appearance_modules,
            appearance_modules_initialized=True,
            custom_webui_dir=payload.custom_webui_dir,
            backup_custom_before_update=payload.backup_custom_before_update,
            impression_prompt=payload.impression_prompt,
        )
    )
    return {"status": "ok", "settings": asdict(saved)}


@app.post("/api/ui/security")
async def ui_save_security(payload: SecurityUpdateRequest, _session: None = Depends(require_web_session)):
    token = security_settings.generate_token() if payload.generate_bot_api_token else payload.bot_api_token
    saved = security_settings.update(
        admin_password=(payload.admin_password or "").strip() or None,
        bot_api_token=token.strip(),
        external_api_enabled=payload.external_api_enabled,
    )
    web_auth.admin_password = saved.admin_password
    web_auth.session_secret = saved.bot_api_token or "development-session-secret"
    return {"status": "ok", "security": _security_payload()}


@app.get("/api/ui/export")
async def ui_export_backup(
    package_type: str = "full",
    module_id: str = "",
    include_security: bool = False,
    _session: None = Depends(require_web_session),
):
    content = backup_service.export_zip(
        package_type=package_type,
        module_id=module_id,
        include_security=include_security,
        nest_version=APP_VERSION,
    )
    package_label = "selected" if "," in package_type else (package_type or "full")
    suffix = f"-{module_id}" if module_id else ""
    filename = f"nest-{package_label}{suffix}.zip"
    return Response(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/ui/import")
async def ui_import_backup(
    backup_file: UploadFile = File(...),
    strategy: str = Form("safe"),
    _session: None = Depends(require_web_session),
):
    payload = await backup_file.read()
    result = backup_service.import_zip(payload, strategy=strategy)
    indexed = diary_service.rebuild_index()
    result["reindexed_diaries"] = indexed
    return {"status": "ok", "result": result}
