from __future__ import annotations

import aiohttp
import asyncio
import os
import shutil
import socket
import sys
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register

from nest_diary_web.diary.diary_service import DiaryService
from nest_diary_web.media.media_service import MediaService
from nest_diary_web.memory.impression_service import ImpressionService
from nest_diary_web.models import DiaryEntry, PersonImpression, ServiceUiSettings
from nest_diary_web.paths import NestPaths
from nest_diary_web.settings_service import SecuritySettingsStore, ServiceSettingsStore


PLUGIN_NAME = "astrbot_plugin_nest_diary_connector"
PLUGIN_VERSION = "0.3.4"


class NestDiaryHttpClient:
    """Compatibility client for users who still run the old standalone service."""

    def __init__(self, service_url: str, token: str, timeout_seconds: int = 30):
        self.service_url = service_url.rstrip("/")
        self.token = token
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def status(self) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(f"{self.service_url}/api/v1/status", headers=self._headers()) as response:
                response.raise_for_status()
                return await response.json()

    async def write_diary(self, payload: dict) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.service_url}/api/v1/diary/write",
                json=payload,
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def read_diary(self, date: str) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(f"{self.service_url}/api/v1/diary/{date}", headers=self._headers()) as response:
                response.raise_for_status()
                return await response.json()

    async def search_diary(self, query: str, top_k: int = 8, snippet_chars: int = 180) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.service_url}/api/v1/diary/search",
                params={"q": query, "top_k": top_k, "snippet_chars": snippet_chars},
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def attach_media(self, payload: dict) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.service_url}/api/v1/media/attach",
                json=payload,
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def list_impressions(self) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(f"{self.service_url}/api/v1/impressions", headers=self._headers()) as response:
                response.raise_for_status()
                return await response.json()

    async def read_impression(self, name: str) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.service_url}/api/v1/impressions/{quote(name, safe='')}",
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def write_impression(self, payload: dict) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.service_url}/api/v1/impressions/write",
                json=payload,
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                return await response.json()


class EmbeddedNestClient:
    """Embedded 小窝核心。插件工具默认直接调用这里，不经过 HTTP。"""

    def __init__(self, data_dir: Path, admin_password: str = "12345678", external_api_key: str = ""):
        self.paths = NestPaths(data_dir)
        self.diary_service = DiaryService(self.paths)
        self.media_service = MediaService(self.paths)
        self.impression_service = ImpressionService(self.paths)
        self.service_settings = ServiceSettingsStore(self.paths)
        self.security_settings = SecuritySettingsStore(
            self.paths,
            default_admin_password=admin_password or "12345678",
            default_bot_api_token=external_api_key,
        )

    async def status(self) -> dict:
        return {
            "status": "ok",
            "service": "embedded-nest",
            "mode": "embedded",
            "data_dir": str(self.paths.root),
            "framework_dir": str(self.paths.framework_dir),
            "modules_dir": str(self.paths.modules_dir),
        }

    async def write_diary(self, payload: dict) -> dict:
        if not self.service_settings.load().enable_diary_module:
            raise RuntimeError("Diary module is disabled")
        entry = DiaryEntry(
            date=payload["date"],
            title=payload.get("title"),
            body=payload["body"],
            mood=payload.get("mood") or [],
            tags=payload.get("tags") or [],
            people=payload.get("people") or [],
            media_refs=payload.get("media_refs") or [],
            importance=payload.get("importance", 3),
            source=payload.get("source", "bot"),
        )
        saved = self.diary_service.write_diary(entry, reason=payload.get("reason", ""))
        return {"status": "ok", "date": saved.date, "title": saved.normalized_title()}

    async def read_diary(self, date: str) -> dict:
        if not self.service_settings.load().enable_diary_module:
            raise RuntimeError("Diary module is disabled")
        entry = self.diary_service.read_by_date(date)
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

    async def search_diary(self, query: str, top_k: int = 8, snippet_chars: int = 180) -> dict:
        if not self.service_settings.load().enable_diary_module:
            raise RuntimeError("Diary module is disabled")
        return {
            "query": query,
            "results": self.diary_service.search(query, top_k=top_k, snippet_chars=snippet_chars),
            "search": self.diary_service.search_status(),
        }

    async def attach_media(self, payload: dict) -> dict:
        if not self.service_settings.load().enable_diary_module:
            raise RuntimeError("Diary module is disabled")
        source = Path(payload["source_path"])
        if not source.exists():
            raise FileNotFoundError(f"Media source file not found: {source}")
        record = self.media_service.save_media(
            source,
            date=payload["date"],
            original_name=payload.get("original_name"),
        )
        return {"status": "ok", "asset": record}

    async def list_impressions(self) -> dict:
        return {"items": [item.__dict__ for item in self.impression_service.list_people()]}

    async def read_impression(self, name: str) -> dict:
        impression = self.impression_service.get(name)
        if not impression:
            raise FileNotFoundError(f"Person impression not found: {name}")
        return impression.__dict__

    async def write_impression(self, payload: dict) -> dict:
        saved = self.impression_service.save(
            PersonImpression(
                name=payload["name"].strip(),
                summary=payload["summary"].strip(),
                traits=payload.get("traits") or [],
                interests=payload.get("interests") or [],
                preferences=payload.get("preferences") or [],
                relationship=(payload.get("relationship") or "").strip(),
                evidence_dates=payload.get("evidence_dates") or [],
                confidence=payload.get("confidence", 3),
                notes=(payload.get("notes") or "").strip(),
            )
        )
        return {"status": "ok", "item": saved.__dict__}


class NestDiaryTools:
    """Bot-native operations. These call embedded 小窝 first unless compatibility mode is selected."""

    def __init__(self, client):
        self.client = client

    async def write_diary(
        self,
        date: str,
        body: str,
        title: str = "",
        mood: list[str] | None = None,
        tags: list[str] | None = None,
        people: list[str] | None = None,
        media_refs: list[str] | None = None,
        reason: str = "",
    ) -> dict:
        return await self.client.write_diary(
            {
                "date": date,
                "title": title or None,
                "body": body,
                "mood": mood or [],
                "tags": tags or [],
                "people": people or [],
                "media_refs": media_refs or [],
                "reason": reason,
                "intent": "write_diary",
                "source": "bot",
            }
        )

    async def read_diary(self, date: str) -> dict:
        return await self.client.read_diary(date)

    async def search_diary(self, query: str, top_k: int = 8, snippet_chars: int = 180) -> dict:
        return await self.client.search_diary(query, top_k=top_k, snippet_chars=snippet_chars)

    async def attach_media(self, source_path: str, date: str, original_name: str | None = None) -> dict:
        return await self.client.attach_media(
            {"source_path": source_path, "date": date, "original_name": original_name}
        )

    async def list_impressions(self) -> dict:
        return await self.client.list_impressions()

    async def read_impression(self, name: str) -> dict:
        return await self.client.read_impression(name)

    async def write_impression(
        self,
        name: str,
        summary: str,
        traits: list[str] | None = None,
        interests: list[str] | None = None,
        preferences: list[str] | None = None,
        relationship: str = "",
        evidence_dates: list[str] | None = None,
        confidence: int = 3,
        notes: str = "",
    ) -> dict:
        return await self.client.write_impression(
            {
                "name": name,
                "summary": summary,
                "traits": traits or [],
                "interests": interests or [],
                "preferences": preferences or [],
                "relationship": relationship,
                "evidence_dates": evidence_dates or [],
                "confidence": confidence,
                "notes": notes,
            }
        )


def _split_words(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace("，", ",").replace("、", ",").replace("；", ",").replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _split_lines(value: str | None) -> list[str]:
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def _brief_error(exc: Exception) -> str:
    if isinstance(exc, aiohttp.ClientResponseError):
        return f"HTTP {exc.status}: {exc.message}"
    return str(exc)


def _is_time_now(now: datetime, configured: str) -> bool:
    try:
        hour_text, minute_text = configured.strip().split(":", 1)
        return now.hour == int(hour_text) and now.minute == int(minute_text)
    except Exception:
        return False


def _default_data_dir() -> Path:
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        astrbot_data = Path(get_astrbot_data_path())
    except Exception:
        astrbot_data = Path("/AstrBot/data") if Path("/AstrBot").exists() else None
    if astrbot_data:
        target = astrbot_data / "plugin_data" / PLUGIN_NAME
        legacy = astrbot_data / "plugins_data" / PLUGIN_NAME
        _copy_missing_tree(legacy, target)
        return target
    return Path(__file__).resolve().parent / "data"


def _configured_data_dir(config: dict) -> Path:
    configured = str(config.get("nest_data_dir", "")).strip()
    return Path(configured) if configured else _default_data_dir()


def _copy_missing_tree(source: Path, target: Path) -> None:
    if not source.exists() or source == target:
        return
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif item.is_file() and not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


@register(
    PLUGIN_NAME,
    "local",
    "小窝框架插件：内置 WebUI、模块化数据目录，以及给 bot 使用的工具层。",
    PLUGIN_VERSION,
)
class NestDiaryConnectorPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        self.mode = self.config.get("nest_mode", "embedded")
        self.data_dir = _configured_data_dir(self.config)
        self.paths = NestPaths(self.data_dir)
        self.diary_module_enabled = bool(self.config.get("enable_diary_module", True))
        self.webui_enabled = bool(self.config.get("enable_webui", True))
        self._last_daily_sent = ""
        self._last_reminder_sent = ""
        self._scheduler_task = None
        self._web_server = None
        self._web_thread = None
        self._webui_started = False
        self._webui_error = ""

        if self.mode == "standalone":
            client = NestDiaryHttpClient(
                service_url=self.config.get("service_url", "http://nest-diary:28080"),
                token=self.config.get("bot_api_token", ""),
                timeout_seconds=int(self.config.get("request_timeout_seconds", 30)),
            )
        else:
            client = EmbeddedNestClient(
                data_dir=self.data_dir,
                admin_password=self.config.get("admin_password", "12345678"),
                external_api_key=self.config.get("bot_api_token", ""),
            )
            self._seed_embedded_settings(client)
            if self.webui_enabled:
                self._start_embedded_webui()

        self.client = client
        self.tools = NestDiaryTools(self.client)

        if self.config.get("scheduled_prompt_enabled", True):
            try:
                self._scheduler_task = asyncio.create_task(self._scheduled_prompt_loop())
            except RuntimeError:
                self._scheduler_task = None

        self._register_plugin_page_api()

    async def terminate(self):
        if self._scheduler_task:
            self._scheduler_task.cancel()
        if self._web_server:
            self._web_server.should_exit = True

    def _register_plugin_page_api(self) -> None:
        if not hasattr(self.context, "register_web_api"):
            return
        try:
            from quart import jsonify
        except Exception:
            return

        async def nest_page_status():
            return jsonify(
                {
                    "plugin": PLUGIN_NAME,
                    "version": PLUGIN_VERSION,
                    "mode": self.mode,
                    "diary_module_enabled": self.diary_module_enabled,
                    "webui_enabled": self.webui_enabled,
                    "webui_started": self._webui_started,
                    "webui_error": self._webui_error,
                    "web_host": self.config.get("web_host", "0.0.0.0"),
                    "web_port": int(self.config.get("web_port", 28080)),
                    "data_dir": str(self.data_dir),
                    "framework_dir": str(self.paths.framework_dir),
                    "modules_dir": str(self.paths.modules_dir),
                    "custom_webui_dir": (
                        str(self.config.get("custom_webui_dir", "")).strip()
                        or str(self.paths.user_custom_dir / "webui")
                    ),
                }
            )

        for route in [
            f"/{PLUGIN_NAME}/status",
            f"/{PLUGIN_NAME}/nest/status",
            f"/{PLUGIN_NAME}/nest-diary/status",
            "/nest/status",
            "nest/status",
            "/nest-diary/status",
            "nest-diary/status",
            "status",
        ]:
            try:
                self.context.register_web_api(route, nest_page_status, ["GET"], "Nest page status")
            except TypeError:
                self.context.register_web_api(route, nest_page_status, ["GET"])
            except Exception:
                continue

    def _seed_embedded_settings(self, client: EmbeddedNestClient) -> None:
        if client.service_settings.path.exists():
            return
        client.service_settings.save(
            ServiceUiSettings(
                enable_diary_module=self.diary_module_enabled,
                search_default_top_k=int(self.config.get("memory_recall_top_k", 5)),
                search_snippet_chars=int(self.config.get("memory_recall_snippet_chars", 180)),
                memory_recall_enabled=bool(self.config.get("memory_recall_enabled", True)),
                memory_recall_policy=self.config.get("memory_recall_policy", "conservative"),
                custom_webui_dir=str(self.config.get("custom_webui_dir", "")).strip(),
                backup_custom_before_update=bool(self.config.get("backup_custom_before_update", True)),
            )
        )

    def _start_embedded_webui(self) -> None:
        try:
            import uvicorn
        except Exception as exc:
            self._webui_error = f"缺少 WebUI 运行依赖：{_brief_error(exc)}"
            return

        host = self.config.get("web_host", "0.0.0.0")
        port = int(self.config.get("web_port", 28080))
        probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((probe_host, port)) == 0:
                    self._webui_error = f"端口 {port} 已被占用"
                    return
        except OSError as exc:
            self._webui_error = f"WebUI 监听地址不可用：{_brief_error(exc)}"
            return

        custom_webui_dir = (
            str(self.config.get("custom_webui_dir", "")).strip()
            or str(self.paths.user_custom_dir / "webui")
        )
        Path(custom_webui_dir).mkdir(parents=True, exist_ok=True)

        os.environ["NEST_DATA_DIR"] = str(self.data_dir)
        os.environ["NEST_ADMIN_PASSWORD"] = self.config.get("admin_password", "12345678")
        os.environ["NEST_BOT_API_TOKEN"] = self.config.get("bot_api_token", "")
        os.environ["NEST_HOST"] = host
        os.environ["NEST_PORT"] = str(port)
        os.environ["NEST_CUSTOM_WEBUI_DIR"] = custom_webui_dir

        try:
            from nest_diary_web.main import app as fastapi_app

            uvicorn_config = uvicorn.Config(
                fastapi_app,
                host=host,
                port=port,
                log_level="warning",
            )
            self._web_server = uvicorn.Server(uvicorn_config)
            self._web_thread = threading.Thread(target=self._web_server.run, daemon=True)
            self._web_thread.start()
            self._webui_started = True
        except Exception as exc:
            self._webui_error = _brief_error(exc)

    @filter.command("小窝状态")
    async def nest_status(self, event: AstrMessageEvent):
        """检查小窝是否在线。"""
        yield event.plain_result(await self._status_message())

    @filter.command("小窝绑定提醒")
    async def bind_nest_prompt_origin(self, event: AstrMessageEvent):
        """显示当前会话 origin，供管理员填入插件配置。"""
        yield event.plain_result(
            "把下面这一串填进插件配置 daily_target_origin，定时提示就会发到当前会话：\n"
            f"{event.unified_msg_origin}"
        )

    @filter.llm_tool(name="nest_status")
    async def nest_status_tool(self, event: AstrMessageEvent):
        """检查小窝框架、日记模块和 WebUI 状态。"""
        return await self._status_message()

    async def _status_message(self) -> str:
        try:
            status = await self.client.status()
            module = "日记模块已启用" if self.diary_module_enabled else "日记模块已关闭"
            recall = "主动回忆已启用" if self.config.get("memory_recall_enabled", True) else "主动回忆已关闭"
            if self._webui_started:
                webui = f"WebUI 已启用：http://{self.config.get('web_host', '0.0.0.0')}:{int(self.config.get('web_port', 28080))}"
            elif self._webui_error:
                webui = f"WebUI 启动失败：{self._webui_error}"
            else:
                webui = "WebUI 未由插件内置启动"
            return (
                f"小窝在线：{status.get('status', 'unknown')}；"
                f"模式：{self.mode}；{module}；{recall}；{webui}；"
                f"数据目录：{self.data_dir}；框架目录：{self.paths.framework_dir}；模块目录：{self.paths.modules_dir}"
            )
        except Exception as exc:
            return f"小窝暂时连接失败：{_brief_error(exc)}"

    def _module_disabled_message(self, module_name: str) -> str:
        return f"{module_name} 模块当前已在插件配置中关闭，未执行工具调用。"

    @filter.llm_tool(name="write_diary")
    async def write_diary_tool(
        self,
        event: AstrMessageEvent,
        date: str,
        title: str,
        body: str,
        mood: str = "",
        tags: str = "",
        people: str = "",
        media_refs: str = "",
        reason: str = "",
    ):
        """写入或更新某一天的日记模块记录。

        Args:
            date(string): 日记日期，格式 YYYY-MM-DD。
            title(string): bot 自拟标题，用一句话概括当天记忆，不要直接使用日期。
            body(string): 日记正文，要包含事件、意义、主观评价、情绪、相关人物和未来线索。
            mood(string): 情绪词，多个用逗号分隔。
            tags(string): 检索标签，多个用逗号分隔。
            people(string): 相关人物，多个用逗号分隔。
            media_refs(string): 图片、语音或附件引用，每行一个，可为空。
            reason(string): 写入原因，例如 nightly_archive、manual_update、memory_review。
        """
        if not self.diary_module_enabled:
            return self._module_disabled_message("日记")
        try:
            result = await self.tools.write_diary(
                date=date,
                title=title,
                body=body,
                mood=_split_words(mood),
                tags=_split_words(tags),
                people=_split_words(people),
                media_refs=_split_lines(media_refs),
                reason=reason,
            )
            saved_date = result.get("date", date)
            saved_title = result.get("title", title)
            revision = result.get("revision_id") or result.get("revision")
            suffix = f"，快照号：{revision}" if revision else ""
            message = f"已写入 {saved_date}《{saved_title}》{suffix}。"
            if self.config.get("auto_impression_after_diary", True):
                prompt = self.config.get("impression_after_diary_prompt", "").strip()
                if prompt:
                    message = f"{message}\n\n人物印象自检提示：{prompt}"
        except Exception as exc:
            message = f"写入日记模块失败：{_brief_error(exc)}"
        return message

    @filter.llm_tool(name="read_diary")
    async def read_diary_tool(self, event: AstrMessageEvent, date: str):
        """读取指定日期的日记。

        Args:
            date(string): 要读取的日期，格式 YYYY-MM-DD。
        """
        if not self.diary_module_enabled:
            return self._module_disabled_message("日记")
        try:
            result = await self.tools.read_diary(date)
            content = result.get("body") or result.get("content") or result.get("text") or ""
            title = result.get("title") or date
            message = f"{date}《{title}》：\n{content}" if content else f"{date} 没有找到日记。"
        except Exception as exc:
            message = f"读取日记模块失败：{_brief_error(exc)}"
        return message

    @filter.llm_tool(name="search_diary")
    async def search_diary_tool(self, event: AstrMessageEvent, query: str, top_k: int = 5):
        """按关键词搜索日记模块，避免一次性读取全部日记。

        Args:
            query(string): 搜索关键词、日期、人物、事件或情绪线索。
            top_k(number): 最多返回多少条结果。工具只返回片段摘要，不返回整篇日记。
        """
        if not self.diary_module_enabled:
            return self._module_disabled_message("日记")
        try:
            limit = max(1, min(int(top_k), int(self.config.get("memory_recall_top_k", 5))))
            snippet_chars = int(self.config.get("memory_recall_snippet_chars", 180))
            result = await self.tools.search_diary(query, top_k=limit, snippet_chars=snippet_chars)
            items = result.get("items") or result.get("results") or []
            if not items:
                message = f"没有搜到和“{query}”相关的日记。"
            else:
                search_info = result.get("search") or {}
                backend = search_info.get("backend", "unknown")
                lines = [f"搜到 {len(items)} 条和“{query}”相关的日记（检索：{backend}）："]
                for item in items:
                    item_date = item.get("date", "未知日期")
                    item_title = item.get("title", "")
                    snippet = item.get("snippet") or item.get("summary") or item.get("body") or ""
                    tags = "，".join(item.get("tags") or [])
                    people = "，".join(item.get("people") or [])
                    meta = "；".join(part for part in [f"人物：{people}" if people else "", f"标签：{tags}" if tags else ""] if part)
                    lines.append(f"- {item_date}《{item_title}》：{snippet}" + (f"（{meta}）" if meta else ""))
                message = "\n".join(lines)
        except Exception as exc:
            message = f"搜索日记模块失败：{_brief_error(exc)}"
        return message

    @filter.llm_tool(name="attach_media")
    async def attach_media_tool(
        self,
        event: AstrMessageEvent,
        source_path: str,
        date: str,
        original_name: str = "",
    ):
        """把图片、语音或附件归档到指定日期的媒体库。

        Args:
            source_path(string): AstrBot 容器内可访问的文件绝对路径。
            date(string): 归档到哪一天，格式 YYYY-MM-DD。
            original_name(string): 原始文件名，可为空。
        """
        if not self.diary_module_enabled:
            return self._module_disabled_message("日记")
        try:
            result = await self.tools.attach_media(source_path=source_path, date=date, original_name=original_name or None)
            asset = result.get("asset") or {}
            media_id = asset.get("url") or asset.get("sha256") or asset.get("path") or result.get("path") or ""
            message = f"已把媒体归档到 {date}：{media_id}"
        except Exception as exc:
            message = f"归档媒体失败：{_brief_error(exc)}"
        return message

    async def _scheduled_prompt_loop(self):
        while True:
            try:
                await self._send_scheduled_prompts_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(60)

    async def _send_scheduled_prompts_once(self):
        origin = self.config.get("daily_target_origin", "").strip()
        if not origin:
            return
        timezone_name = self.config.get("timezone", "Asia/Shanghai")
        now = datetime.now(ZoneInfo(timezone_name))
        today_key = now.strftime("%Y-%m-%d")
        if self.diary_module_enabled and self.config.get("daily_write_enabled", True):
            daily_time = self.config.get("daily_write_time", "03:00")
            if _is_time_now(now, daily_time) and self._last_daily_sent != today_key:
                prompt = self.config.get("daily_write_prompt", "").strip()
                if prompt:
                    await self.context.send_message(origin, MessageChain().message(prompt))
                    self._last_daily_sent = today_key
        if self.config.get("reminder_enabled", False):
            reminder_time = self.config.get("reminder_time", "23:30")
            if _is_time_now(now, reminder_time) and self._last_reminder_sent != today_key:
                prompt = self.config.get("reminder_prompt", "").strip()
                if prompt:
                    await self.context.send_message(origin, MessageChain().message(prompt))
                    self._last_reminder_sent = today_key

    @filter.llm_tool(name="list_impressions")
    async def list_impressions_tool(self, event: AstrMessageEvent):
        """列出小窝中已经记录的人物印象摘要。"""
        try:
            result = await self.tools.list_impressions()
            items = result.get("items") or []
            if not items:
                message = "还没有记录任何人物印象。"
            else:
                lines = [f"已有 {len(items)} 条人物印象："]
                for item in items:
                    lines.append(f"- {item.get('name', '未知')}：{item.get('summary', '')}")
                message = "\n".join(lines)
        except Exception as exc:
            message = f"读取人物印象列表失败：{_brief_error(exc)}"
        return message

    @filter.llm_tool(name="read_impression")
    async def read_impression_tool(self, event: AstrMessageEvent, name: str):
        """读取指定人物的长期印象。

        Args:
            name(string): 人物名。
        """
        try:
            item = await self.tools.read_impression(name)
            parts = [f"{item.get('name', name)} 的人物印象：", item.get("summary", "")]
            if item.get("traits"):
                parts.append("性格：" + "，".join(item["traits"]))
            if item.get("interests"):
                parts.append("兴趣：" + "，".join(item["interests"]))
            if item.get("preferences"):
                parts.append("偏好：" + "，".join(item["preferences"]))
            if item.get("relationship"):
                parts.append("关系：" + item["relationship"])
            if item.get("evidence_dates"):
                parts.append("证据日期：" + "，".join(item["evidence_dates"]))
            message = "\n".join(part for part in parts if part)
        except Exception as exc:
            message = f"读取人物印象失败：{_brief_error(exc)}"
        return message

    @filter.llm_tool(name="write_impression")
    async def write_impression_tool(
        self,
        event: AstrMessageEvent,
        name: str,
        summary: str,
        traits: str = "",
        interests: str = "",
        preferences: str = "",
        relationship: str = "",
        evidence_dates: str = "",
        confidence: int = 3,
        notes: str = "",
    ):
        """写入或更新指定人物的长期印象。

        Args:
            name(string): 人物名。
            summary(string): 对这个人的稳定总结，必须基于可追溯证据。
            traits(string): 性格特征，多个用逗号分隔。
            interests(string): 兴趣爱好，多个用逗号分隔。
            preferences(string): 偏好或相处方式，多个用逗号分隔。
            relationship(string): 与 bot 或项目的关系。
            evidence_dates(string): 支撑这次更新的日记日期，多个用逗号分隔。
            confidence(number): 可信度，1 到 5。
            notes(string): 额外备注。
        """
        try:
            result = await self.tools.write_impression(
                name=name,
                summary=summary,
                traits=_split_words(traits),
                interests=_split_words(interests),
                preferences=_split_words(preferences),
                relationship=relationship,
                evidence_dates=_split_words(evidence_dates),
                confidence=int(confidence),
                notes=notes,
            )
            item = result.get("item") or {}
            message = f"已更新 {item.get('name', name)} 的人物印象。"
        except Exception as exc:
            message = f"写入人物印象失败：{_brief_error(exc)}"
        return message
