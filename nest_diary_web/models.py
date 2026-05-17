from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DiaryEntry:
    date: str
    body: str
    title: str | None = None
    mood: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    media_refs: list[str] = field(default_factory=list)
    importance: int = 3
    source: str = "bot"
    revision: int = 1

    def normalized_title(self) -> str:
        return self.title or self.date


@dataclass
class PersonImpression:
    name: str
    summary: str
    traits: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    relationship: str = ""
    evidence_dates: list[str] = field(default_factory=list)
    confidence: int = 3
    notes: str = ""
    updated_at: str = ""


@dataclass
class ServiceUiSettings:
    enable_diary_module: bool = True
    search_default_top_k: int = 20
    diary_archive_granularity: str = "day"
    allow_media_refs: bool = True
    show_impression_prompt: bool = True
    active_frontend_style: str = "default"
    custom_webui_dir: str = ""
    backup_custom_before_update: bool = True
    impression_prompt: str = (
        "写完日记后，请依据你的角色设定和当天日记内容判断："
        "这篇日记是否提供了关于某个人的稳定新证据。"
        "如果有，请更新人物印象；如果没有，不要硬写。"
    )


@dataclass
class SecuritySettings:
    admin_password: str = "12345678"
    bot_api_token: str = ""
    external_api_enabled: bool = False
