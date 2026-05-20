from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DiaryEntry:
    date: str
    body: str
    title: str | None = None
    notebook_id: str = "default"
    notebook_name: str = "默认日记本"
    origin_umo: str = ""
    platform_id: str = ""
    message_type: str = ""
    session_id: str = ""
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
    identity: str = ""
    traits: list[str] = field(default_factory=list)
    hobbies: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    relationship: str = ""
    affinity: int = 3
    special_comment: str = ""
    evidence_dates: list[str] = field(default_factory=list)
    confidence: int = 3
    notes: str = ""
    updated_at: str = ""


@dataclass
class ServiceUiSettings:
    site_title: str = "小窝"
    site_subtitle: str = "把今天安放好，旧事也能被轻轻找回来"
    brand_avatar_url: str = ""
    enable_diary_module: bool = True
    search_default_top_k: int = 5
    search_snippet_chars: int = 180
    memory_recall_enabled: bool = True
    memory_recall_policy: str = "conservative"
    diary_archive_granularity: str = "day"
    diary_display_mode: str = "grouped"
    admin_private_diary_enabled: bool = False
    admin_private_push_enabled: bool = False
    diary_push_format: str = "text"
    diary_push_target: str = "none"
    permissions_allow_admin_natural_language: bool = True
    non_admin_permissions: list[str] = field(default_factory=list)
    nest_admin_ids: str = ""
    diary_write_prompt: str = (
        "请把可用上下文整理成一篇小窝日记。标题要概括当天记忆的意义；正文要包含发生了什么、"
        "为什么重要、你的主观评价与情绪、相关人物、未来线索。不要写成聊天流水账，不要编造。"
    )
    diary_t2i_template: str = (
        "<div style=\"font-family:'Microsoft YaHei',sans-serif;width:760px;padding:42px;"
        "background:#fffdf8;color:#20242a;border:2px solid #20242a;\">"
        "<p style=\"margin:0 0 12px;color:#176f66;font-weight:800;\">{{ date }} · {{ notebook_name }}</p>"
        "<h1 style=\"margin:0 0 22px;font-size:34px;line-height:1.2;\">{{ title }}</h1>"
        "<div style=\"white-space:pre-wrap;font-size:20px;line-height:1.75;\">{{ body }}</div>"
        "</div>"
    )
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
    enabled_official_modules: list[str] = field(default_factory=lambda: ["diary", "impressions", "media", "webui"])
    enabled_custom_modules: list[str] = field(default_factory=list)
    enabled_custom_extensions: list[str] = field(default_factory=list)
    enabled_appearance_modules: list[str] = field(default_factory=list)
    appearance_modules_initialized: bool = False
    custom_webui_dir: str = ""
    backup_custom_before_update: bool = True
    impression_prompt: str = (
        "写完日记后，请依据你的角色设定和当天日记内容判断："
        "这篇日记是否提供了关于某个人的稳定新证据。"
        "如果有，请先读取旧人物印象，再按变化更新 name、identity、summary、traits、hobbies、interests、preferences、relationship、affinity、special_comment、evidence_dates、confidence、notes；"
        "summary 写稳定总结，special_comment 写带有主观判断的特殊点评。"
        "如果没有稳定变化，不要硬写。"
    )


@dataclass
class SecuritySettings:
    admin_password: str = "12345678"
    bot_api_token: str = ""
    external_api_enabled: bool = False
