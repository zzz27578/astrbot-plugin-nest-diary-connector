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
    qq_id: str = ""
    group_impressions: list[dict] = field(default_factory=list)
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
class MemoEntry:
    id: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    source_chat: str = ""
    origin_umo: str = ""
    platform_id: str = ""
    message_type: str = ""
    session_id: str = ""
    recorder: str = "human"
    source: str = "manual"
    sensitive: bool = False
    pinned: bool = False
    archived: bool = False
    created_at: str = ""
    updated_at: str = ""
    deleted_at: str = ""


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
    diary_t2i_template_name: str = "plain_note"
    diary_image_send_max_retries: int = 3
    diary_image_send_failure_notice: bool = True
    permissions_allow_admin_natural_language: bool = True
    non_admin_permissions: list[str] = field(default_factory=list)
    nest_admin_ids: str = ""
    diary_write_prompt: str = (
        "请把可用上下文整理成一篇小窝日记。标题要概括当天记忆的意义；正文要包含发生了什么、"
        "为什么重要、你的主观评价与情绪、相关人物、未来线索。不要写成聊天流水账，不要编造。"
    )
    diary_t2i_template: str = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><style>"
        "html,body{margin:0;padding:0;width:760px;background:transparent;}"
        "body{font-family:'Microsoft YaHei','Noto Sans SC',sans-serif;color:#20242a;}"
        ".diary-push-page{box-sizing:border-box;width:760px;min-height:360px;padding:46px 50px 52px;"
        "background:#fffdf8;border:2px solid #20242a;}"
        ".meta{margin:0 0 14px;color:#176f66;font-size:18px;line-height:1.4;font-weight:800;}"
        "h1{margin:0 0 24px;font-size:34px;line-height:1.22;font-weight:900;letter-spacing:0;}"
        ".body{white-space:pre-wrap;font-size:20px;line-height:1.78;word-break:break-word;}"
        ".rule{width:70px;height:5px;background:#176f66;margin:0 0 22px;}"
        "</style></head><body><main class=\"diary-push-page\">"
        "<div class=\"rule\"></div><p class=\"meta\">{{ date }} · {{ notebook_name }}</p>"
        "<h1>{{ title }}</h1><div class=\"body\">{{ body }}</div>"
        "</main></body></html>"
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
    impression_identity_strategy: str = "separate"
    impression_allow_new_people: bool = False
    impression_min_confidence: int = 3
    show_impression_prompt: bool = True
    enable_memos_module: bool = True
    memos_write_policy: str = "admin_only"
    memos_auto_write_limit_12h: int = 12
    memos_sensitive_default_hidden: bool = True
    active_frontend_style: str = "default"
    enabled_official_modules: list[str] = field(default_factory=lambda: ["diary", "impressions", "media", "memos", "webui"])
    enabled_custom_modules: list[str] = field(default_factory=list)
    enabled_custom_extensions: list[str] = field(default_factory=list)
    enabled_appearance_modules: list[str] = field(default_factory=list)
    appearance_modules_initialized: bool = False
    onboarding_completed: bool = False
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
