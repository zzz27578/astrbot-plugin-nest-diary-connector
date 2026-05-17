from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .auth import verify_bearer_token_from_store
from .backup_service import BackupService
from .config import load_settings
from .diary.diary_service import DiaryService
from .memory.impression_service import ImpressionService
from .media.media_service import MediaService
from .models import DiaryEntry, PersonImpression
from .paths import NestPaths
from .settings_service import SecuritySettingsStore, ServiceSettingsStore
from .version_service import VersionService
from .web.routes import create_web_router, mount_static
from .web_auth import WebSessionAuth

APP_VERSION = "0.2.2"
settings = load_settings()
app = FastAPI(title="Nest Diary Service", version=APP_VERSION)
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
mount_static(app)
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
