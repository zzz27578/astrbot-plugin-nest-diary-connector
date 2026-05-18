from __future__ import annotations

import json
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

APP_VERSION = "0.3.9"
settings = load_settings()
app = FastAPI(title="Nest Service", version=APP_VERSION)
WEB_DIST_DIR = Path(__file__).resolve().parent / "web_dist"
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
        "date": entry.date,
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
    return {
        "official": official,
        "custom": custom,
        "extensions": extensions,
        "conflicts": _module_conflicts(ui_settings, official, custom, extensions),
    }


def _discover_official_modules() -> list[dict]:
    modules_root = Path(__file__).resolve().parents[1] / "modules"
    modules: list[dict] = []
    for module_id in ["diary", "impressions", "media", "webui"]:
        modules.append(
            _load_package_manifest(
                modules_root / module_id / "module.json",
                {
                    "id": module_id,
                    "name": module_id,
                    "type": "module",
                    "description": "",
                    "feature_tags": [f"{module_id}-core"],
                    "replaces": [],
                    "conflicts_with": [],
                },
                kind="official",
            )
        )
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


def _module_conflicts(ui_settings: ServiceUiSettings, official: list[dict], custom: list[dict], extensions: list[dict]) -> list[dict]:
    enabled: list[dict] = []
    enabled.extend(item for item in official if item["id"] in ui_settings.enabled_official_modules)
    enabled.extend(item for item in custom if item["id"] in ui_settings.enabled_custom_modules)
    enabled.extend(item for item in extensions if item["id"] in ui_settings.enabled_custom_extensions)

    warnings: list[dict] = []
    by_id = {item["id"]: item for item in enabled}
    by_tag: dict[str, list[str]] = {}
    for item in enabled:
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
    return warnings


class DiaryWriteRequest(BaseModel):
    date: str
    body: str
    title: str | None = None
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
    entry = DiaryEntry(
        date=payload.date,
        title=payload.title,
        body=payload.body,
        mood=payload.mood,
        tags=payload.tags,
        people=payload.people,
        media_refs=payload.media_refs,
        importance=payload.importance,
        source=payload.source,
    )
    saved = diary_service.write_diary(entry, reason=payload.reason)
    touched = impression_service.touch_from_diary(saved)
    return {
        "status": "ok",
        "date": saved.date,
        "title": saved.normalized_title(),
        "impressions_touched": [item.name for item in touched],
    }


@app.get("/api/v1/diary/search")
async def search_diary(
    q: str,
    top_k: int = 8,
    snippet_chars: int = 180,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    return {
        "query": q,
        "results": diary_service.search(q, top_k=top_k, snippet_chars=snippet_chars),
        "search": diary_service.search_status(),
    }


@app.get("/api/v1/diary/archive")
async def diary_archive(
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    return {"items": diary_service.archive_tree()}


@app.get("/api/v1/diary/{date}")
async def read_diary(
    date: str,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    try:
        entry = diary_service.read_by_date(date)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Diary entry not found") from None
    return {
        "date": entry.date,
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


@app.post("/api/v1/media/attach")
async def attach_media(
    payload: MediaAttachRequest,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    source = Path(payload.source_path)
    if not source.exists():
        raise HTTPException(status_code=404, detail="Media source file not found")
    record = media_service.save_media(source, date=payload.date, original_name=payload.original_name)
    return {"status": "ok", "asset": record}


@app.get("/api/v1/media/by-date/{date}")
async def list_media_by_date(
    date: str,
    _auth: None = Depends(require_bot_token),
    _module: None = Depends(require_diary_module_enabled),
):
    return media_service.list_by_date(date)


@app.get("/media/blobs/{digest}")
async def read_media_blob(digest: str):
    blob = media_service.find_blob(digest)
    if not blob:
        raise HTTPException(status_code=404, detail="Media blob not found")
    return FileResponse(blob)


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
    brand_avatar_url: str = ""
    search_default_top_k: int = 5
    search_snippet_chars: int = 180
    memory_recall_enabled: bool = True
    memory_recall_policy: str = "conservative"
    enable_diary_module: bool = True
    diary_archive_granularity: str = "day"
    allow_media_refs: bool = True
    show_impression_prompt: bool = True
    active_frontend_style: str = "default"
    enabled_official_modules: list[str] = Field(default_factory=lambda: ["diary", "impressions", "media", "webui"])
    enabled_custom_modules: list[str] = Field(default_factory=list)
    enabled_custom_extensions: list[str] = Field(default_factory=list)
    custom_webui_dir: str = ""
    backup_custom_before_update: bool = True
    impression_prompt: str = ""


class SecurityUpdateRequest(BaseModel):
    admin_password: str | None = None
    bot_api_token: str = ""
    generate_bot_api_token: bool = False
    external_api_enabled: bool = False


@app.get("/api/v1/impressions")
async def list_impressions(_auth: None = Depends(require_bot_token)):
    return {"items": [item.__dict__ for item in impression_service.list_people()]}


@app.get("/api/v1/impressions/{name}")
async def read_impression(name: str, _auth: None = Depends(require_bot_token)):
    impression = impression_service.get(name)
    if not impression:
        raise HTTPException(status_code=404, detail="Person impression not found")
    return impression.__dict__


@app.post("/api/v1/impressions/write")
async def write_impression(payload: ImpressionWriteRequest, _auth: None = Depends(require_bot_token)):
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
async def delete_impression(name: str, _auth: None = Depends(require_bot_token)):
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
        "settings": _settings_payload(),
        "security": _security_payload(),
        "search": diary_service.search_status(),
        "frontend_styles": _frontend_styles(ui_settings),
        "module_catalog": _module_catalog(ui_settings),
        "data_dir": str(settings.data_dir),
        "framework_dir": str(paths.framework_dir),
        "modules_dir": str(paths.modules_dir),
    }


@app.get("/api/ui/diary")
async def ui_list_diary(_session: None = Depends(require_web_session)):
    return {
        "items": [_entry_payload(entry) for entry in diary_service.list_entries()],
        "archive": diary_service.archive_tree(),
    }


@app.get("/api/ui/diary/{date}")
async def ui_read_diary(date: str, _session: None = Depends(require_web_session)):
    try:
        return _entry_payload(diary_service.read_by_date(date))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Diary entry not found") from None


@app.post("/api/ui/diary")
async def ui_write_diary(payload: DiaryWriteRequest, _session: None = Depends(require_web_session)):
    if not service_settings.load().enable_diary_module:
        raise HTTPException(status_code=403, detail="Diary module is disabled")
    entry = DiaryEntry(
        date=payload.date,
        title=payload.title,
        body=payload.body,
        mood=payload.mood,
        tags=payload.tags,
        people=payload.people,
        media_refs=payload.media_refs,
        importance=payload.importance,
        source=payload.source or "admin",
    )
    saved = diary_service.write_diary(entry, reason=payload.reason or "web_app_update")
    touched = impression_service.touch_from_diary(saved)
    return {"status": "ok", "entry": _entry_payload(saved), "impressions_touched": [item.name for item in touched]}


@app.delete("/api/ui/diary/{date}")
async def ui_delete_diary(date: str, _session: None = Depends(require_web_session)):
    deleted = diary_service.delete_diary(date, reason="web_app_delete")
    if not deleted:
        raise HTTPException(status_code=404, detail="Diary entry not found")
    return {"status": "ok"}


@app.get("/api/ui/search")
async def ui_search(q: str = "", top_k: int = 5, _session: None = Depends(require_web_session)):
    ui_settings = service_settings.load()
    if not q or not ui_settings.enable_diary_module:
        return {"query": q, "results": [], "search": diary_service.search_status()}
    return {
        "query": q,
        "results": diary_service.search(q, top_k=top_k or ui_settings.search_default_top_k, snippet_chars=ui_settings.search_snippet_chars),
        "search": diary_service.search_status(),
    }


@app.get("/api/ui/impressions")
async def ui_list_impressions(_session: None = Depends(require_web_session)):
    return {"items": [item.__dict__ for item in impression_service.list_people()]}


@app.get("/api/ui/impressions/{name}")
async def ui_read_impression(name: str, _session: None = Depends(require_web_session)):
    impression = impression_service.get(name)
    if not impression:
        raise HTTPException(status_code=404, detail="Person impression not found")
    return impression.__dict__


@app.post("/api/ui/impressions")
async def ui_write_impression(payload: ImpressionWriteRequest, _session: None = Depends(require_web_session)):
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
    if not impression_service.delete(name):
        raise HTTPException(status_code=404, detail="Person impression not found")
    return {"status": "ok"}


@app.get("/api/ui/media")
async def ui_media(_session: None = Depends(require_web_session)):
    return {"items": media_service.list_manifests()}


@app.get("/api/ui/settings")
async def ui_get_settings(_session: None = Depends(require_web_session)):
    ui_settings = service_settings.load()
    return {
        "settings": _settings_payload(),
        "security": _security_payload(),
        "search": diary_service.search_status(),
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
            brand_avatar_url=payload.brand_avatar_url,
            search_default_top_k=payload.search_default_top_k,
            search_snippet_chars=payload.search_snippet_chars,
            memory_recall_enabled=payload.memory_recall_enabled,
            memory_recall_policy=payload.memory_recall_policy,
            enable_diary_module=payload.enable_diary_module,
            diary_archive_granularity=payload.diary_archive_granularity,
            allow_media_refs=payload.allow_media_refs,
            show_impression_prompt=payload.show_impression_prompt,
            active_frontend_style=payload.active_frontend_style,
            enabled_official_modules=payload.enabled_official_modules,
            enabled_custom_modules=payload.enabled_custom_modules,
            enabled_custom_extensions=payload.enabled_custom_extensions,
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
    suffix = f"-{module_id}" if module_id else ""
    filename = f"nest-{package_type}{suffix}.zip"
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
