from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
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

APP_VERSION = "0.3.2"
settings = load_settings()
app = FastAPI(title="Nest Diary Service", version=APP_VERSION)
WEB_DIST_DIR = Path(__file__).resolve().parent / "web_dist"
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
    custom_env = settings.data_dir / "user_custom" / "webui"
    return custom_env


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
    custom_modules = []
    modules_dir = _custom_webui_root(ui_settings) / "modules"
    if modules_dir.exists():
        for path in sorted(modules_dir.iterdir()):
            if path.is_dir():
                custom_modules.append({"id": path.name, "name": path.name, "path": str(path)})
    return {
        "official": [
            {"id": "diary", "name": "日记", "description": "写入、读取、归档和检索"},
            {"id": "impressions", "name": "人物印象", "description": "长期人物认识"},
            {"id": "media", "name": "媒体", "description": "图片、语音和附件归档"},
            {"id": "webui", "name": "WebUI", "description": "网页后台与设置页"},
        ],
        "custom": custom_modules,
    }


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
        "service": "nest-diary",
        "version": APP_VERSION,
        "data_dir": str(settings.data_dir),
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
    return {"status": "ok", "date": saved.date, "title": saved.normalized_title()}


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
    name: str
    summary: str
    traits: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    relationship: str = ""
    evidence_dates: list[str] = Field(default_factory=list)
    confidence: int = 3
    notes: str = ""


class SettingsUpdateRequest(BaseModel):
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
    saved = impression_service.save(
        PersonImpression(
            name=payload.name.strip(),
            summary=payload.summary.strip(),
            traits=payload.traits,
            interests=payload.interests,
            preferences=payload.preferences,
            relationship=payload.relationship.strip(),
            evidence_dates=payload.evidence_dates,
            confidence=payload.confidence,
            notes=payload.notes.strip(),
        )
    )
    return {"status": "ok", "item": saved.__dict__}


@app.get("/api/ui/bootstrap")
async def ui_bootstrap(_session: None = Depends(require_web_session)):
    ui_settings = service_settings.load()
    entries = diary_service.list_entries()
    media = media_service.list_manifests()
    people = impression_service.list_people()
    return {
        "version": APP_VERSION,
        "service": "nest-diary",
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
    return {"status": "ok", "entry": _entry_payload(saved)}


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
    saved = impression_service.save(
        PersonImpression(
            name=payload.name.strip(),
            summary=payload.summary.strip(),
            traits=payload.traits,
            interests=payload.interests,
            preferences=payload.preferences,
            relationship=payload.relationship.strip(),
            evidence_dates=payload.evidence_dates,
            confidence=payload.confidence,
            notes=payload.notes.strip(),
        )
    )
    return {"status": "ok", "item": saved.__dict__}


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
            "port": settings.port,
            "self_update": settings.enable_self_update,
        },
    }


@app.post("/api/ui/settings")
async def ui_save_settings(payload: SettingsUpdateRequest, _session: None = Depends(require_web_session)):
    saved = service_settings.save(
        ServiceUiSettings(
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
