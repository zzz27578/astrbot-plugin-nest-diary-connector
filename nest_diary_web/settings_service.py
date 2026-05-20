from __future__ import annotations

import json
import secrets
from dataclasses import asdict

from nest_diary_web.models import SecuritySettings, ServiceUiSettings
from nest_diary_web.paths import NestPaths


class ServiceSettingsStore:
    def __init__(self, paths: NestPaths):
        self.paths = paths
        self.paths.ensure_all()
        self.path = self.paths.settings_dir / "service-ui.json"

    def load(self) -> ServiceUiSettings:
        if not self.path.exists():
            return self._normalize(ServiceUiSettings())
        data = json.loads(self.path.read_text(encoding="utf-8"))
        defaults = asdict(ServiceUiSettings())
        defaults.update(data)
        return self._normalize(ServiceUiSettings(**defaults))

    def save(self, settings: ServiceUiSettings) -> ServiceUiSettings:
        settings = self._normalize(settings)
        self.path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return settings

    def _normalize(self, settings: ServiceUiSettings) -> ServiceUiSettings:
        settings.site_title = (settings.site_title or "").strip() or "小窝"
        settings.site_subtitle = (settings.site_subtitle or "").strip() or "把今天安放好，旧事也能被轻轻找回来"
        settings.brand_avatar_url = (settings.brand_avatar_url or "").strip()
        settings.enable_diary_module = bool(settings.enable_diary_module)
        settings.search_default_top_k = max(1, min(int(settings.search_default_top_k), 20))
        settings.search_snippet_chars = max(80, min(int(settings.search_snippet_chars), 360))
        settings.memory_recall_enabled = bool(settings.memory_recall_enabled)
        if settings.memory_recall_policy not in {"conservative", "active"}:
            settings.memory_recall_policy = "conservative"
        if settings.diary_archive_granularity not in {"day", "month", "year"}:
            settings.diary_archive_granularity = "day"
        if settings.diary_display_mode not in {"grouped", "merged"}:
            settings.diary_display_mode = "grouped"
        settings.admin_private_diary_enabled = bool(settings.admin_private_diary_enabled)
        settings.admin_private_push_enabled = bool(settings.admin_private_push_enabled)
        if settings.diary_push_format not in {"text", "image"}:
            settings.diary_push_format = "text"
        if settings.diary_push_target not in {"source", "admin_private", "both"}:
            settings.diary_push_target = "admin_private"
        settings.permissions_allow_admin_natural_language = bool(settings.permissions_allow_admin_natural_language)
        settings.nest_admin_ids = "\n".join(
            dict.fromkeys(
                item.strip()
                for item in str(settings.nest_admin_ids or "").replace(",", "\n").replace("，", "\n").splitlines()
                if item.strip()
            )
        )
        settings.enable_media_module = bool(settings.enable_media_module)
        settings.allow_media_refs = bool(settings.allow_media_refs)
        settings.media_max_items_per_day = max(1, min(int(settings.media_max_items_per_day), 500))
        settings.media_auto_save_policy = {"manual": "admin_allowed", "bot_pick": "bot_curated"}.get(
            settings.media_auto_save_policy,
            settings.media_auto_save_policy,
        )
        if settings.media_auto_save_policy not in {"admin_only", "admin_allowed", "bot_curated", "review"}:
            settings.media_auto_save_policy = "admin_only"
        settings.media_auto_save_limit_12h = max(0, min(int(settings.media_auto_save_limit_12h), 200))
        if settings.media_auto_album_strategy not in {"off", "existing_only", "confirm", "auto"}:
            settings.media_auto_album_strategy = "confirm"
        settings.media_allow_bot_import = bool(settings.media_allow_bot_import)
        settings.media_auto_album = bool(settings.media_auto_album)
        if settings.media_auto_album_strategy == "off":
            settings.media_auto_album = False
        if settings.media_storage_strategy not in {"copy", "move", "cut"}:
            settings.media_storage_strategy = "copy"
        if settings.media_storage_strategy == "cut":
            settings.media_storage_strategy = "move"
        settings.enable_impressions_module = bool(settings.enable_impressions_module)
        settings.auto_impression_from_diary = bool(settings.auto_impression_from_diary)
        if settings.impression_write_level not in {"off", "light", "balanced", "deep"}:
            settings.impression_write_level = "balanced"
        if settings.impression_update_strategy not in {"manual", "evidence_only", "existing_only", "aggressive"}:
            settings.impression_update_strategy = "evidence_only"
        settings.impression_allow_new_people = bool(settings.impression_allow_new_people)
        settings.impression_min_confidence = max(1, min(int(settings.impression_min_confidence), 5))
        if settings.impression_write_level == "off":
            settings.auto_impression_from_diary = False
        if settings.impression_update_strategy in {"manual", "existing_only"}:
            settings.impression_allow_new_people = False
        settings.show_impression_prompt = bool(settings.show_impression_prompt)
        settings.active_frontend_style = (settings.active_frontend_style or "").strip() or "default"
        if not isinstance(settings.enabled_official_modules, list):
            settings.enabled_official_modules = ["diary", "impressions", "media", "webui"]
        if not isinstance(settings.enabled_custom_modules, list):
            settings.enabled_custom_modules = []
        if not isinstance(settings.enabled_custom_extensions, list):
            settings.enabled_custom_extensions = []
        if not isinstance(settings.enabled_appearance_modules, list):
            settings.enabled_appearance_modules = []
        settings.appearance_modules_initialized = bool(settings.appearance_modules_initialized)
        if not settings.appearance_modules_initialized:
            settings.appearance_modules_initialized = True
        settings.enabled_official_modules = [
            item for item in settings.enabled_official_modules if item in {"diary", "impressions", "media", "webui"}
        ]
        settings.enabled_official_modules = [
            item
            for item in settings.enabled_official_modules
            if item != "media" or settings.enable_media_module
        ]
        if settings.enable_media_module and "media" not in settings.enabled_official_modules:
            settings.enabled_official_modules.append("media")
        if not settings.enable_media_module:
            settings.allow_media_refs = False
            settings.media_allow_bot_import = False
            settings.media_auto_album = False
        settings.enabled_custom_modules = [
            item.strip() for item in settings.enabled_custom_modules if self._safe_package_id(item.strip())
        ]
        settings.enabled_custom_extensions = [
            item.strip() for item in settings.enabled_custom_extensions if self._safe_package_id(item.strip())
        ]
        settings.enabled_appearance_modules = [
            item.strip() for item in settings.enabled_appearance_modules if self._safe_package_id(item.strip())
        ]
        settings.custom_webui_dir = (settings.custom_webui_dir or "").strip()
        settings.backup_custom_before_update = bool(settings.backup_custom_before_update)
        settings.impression_prompt = settings.impression_prompt or ""
        return settings

    def _safe_package_id(self, value: str) -> bool:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
        return bool(value) and all(char in allowed for char in value)


class SecuritySettingsStore:
    def __init__(self, paths: NestPaths, default_admin_password: str = "12345678", default_bot_api_token: str = ""):
        self.paths = paths
        self.paths.ensure_all()
        self.path = self.paths.settings_dir / "security.json"
        self.default_admin_password = default_admin_password or "12345678"
        self.default_bot_api_token = default_bot_api_token

    def load(self) -> SecuritySettings:
        defaults = {
            "admin_password": self.default_admin_password,
            "bot_api_token": self.default_bot_api_token,
            "external_api_enabled": bool(self.default_bot_api_token),
        }
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            defaults.update(data)
        return SecuritySettings(**defaults)

    def save(self, settings: SecuritySettings) -> SecuritySettings:
        settings.admin_password = settings.admin_password or self.default_admin_password
        self.path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return settings

    def update(
        self,
        admin_password: str | None = None,
        bot_api_token: str | None = None,
        external_api_enabled: bool | None = None,
    ) -> SecuritySettings:
        current = self.load()
        if admin_password:
            current.admin_password = admin_password
        if bot_api_token is not None:
            current.bot_api_token = bot_api_token
        if external_api_enabled is not None:
            current.external_api_enabled = external_api_enabled
        return self.save(current)

    def generate_token(self) -> str:
        return secrets.token_urlsafe(32)
