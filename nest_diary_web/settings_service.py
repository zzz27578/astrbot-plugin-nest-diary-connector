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
        settings.brand_avatar_url = (settings.brand_avatar_url or "").strip()
        settings.enable_diary_module = bool(settings.enable_diary_module)
        settings.search_default_top_k = max(1, min(int(settings.search_default_top_k), 20))
        settings.search_snippet_chars = max(80, min(int(settings.search_snippet_chars), 360))
        settings.memory_recall_enabled = bool(settings.memory_recall_enabled)
        if settings.memory_recall_policy not in {"conservative", "active"}:
            settings.memory_recall_policy = "conservative"
        if settings.diary_archive_granularity not in {"day", "month", "year"}:
            settings.diary_archive_granularity = "day"
        settings.allow_media_refs = bool(settings.allow_media_refs)
        settings.show_impression_prompt = bool(settings.show_impression_prompt)
        settings.active_frontend_style = (settings.active_frontend_style or "").strip() or "default"
        if not isinstance(settings.enabled_official_modules, list):
            settings.enabled_official_modules = ["diary", "impressions", "media", "webui"]
        if not isinstance(settings.enabled_custom_modules, list):
            settings.enabled_custom_modules = []
        if not isinstance(settings.enabled_custom_extensions, list):
            settings.enabled_custom_extensions = []
        settings.enabled_official_modules = [
            item for item in settings.enabled_official_modules if item in {"diary", "impressions", "media", "webui"}
        ]
        settings.enabled_custom_modules = [
            item.strip() for item in settings.enabled_custom_modules if self._safe_package_id(item.strip())
        ]
        settings.enabled_custom_extensions = [
            item.strip() for item in settings.enabled_custom_extensions if self._safe_package_id(item.strip())
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
