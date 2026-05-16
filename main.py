from __future__ import annotations

import asyncio
import aiohttp
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register


PLUGIN_NAME = "astrbot_plugin_nest_diary_connector"


class NestDiaryClient:
    def __init__(self, service_url: str, token: str, timeout_seconds: int = 30):
        self.service_url = service_url.rstrip("/")
        self.token = token
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    async def status(self) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.service_url}/api/v1/status",
                headers=self._headers(),
            ) as response:
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
            async with session.get(
                f"{self.service_url}/api/v1/diary/{date}",
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def search_diary(self, query: str, top_k: int = 8) -> dict:
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.service_url}/api/v1/diary/search",
                params={"q": query, "top_k": top_k},
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
            async with session.get(
                f"{self.service_url}/api/v1/impressions",
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def read_impression(self, name: str) -> dict:
        safe_name = quote(name, safe="")
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.service_url}/api/v1/impressions/{safe_name}",
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


class NestDiaryTools:
    """Bot-native operations. These call the nest service instead of touching files."""

    def __init__(self, client: NestDiaryClient):
        self.client = client

    async def write_diary(
        self,
        date: str,
        body: str,
        mood: list[str] | None = None,
        tags: list[str] | None = None,
        people: list[str] | None = None,
        media_refs: list[str] | None = None,
        reason: str = "",
    ) -> dict:
        return await self.client.write_diary(
            {
                "date": date,
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

    async def search_diary(self, query: str, top_k: int = 8) -> dict:
        return await self.client.search_diary(query, top_k=top_k)

    async def attach_media(self, source_path: str, date: str, original_name: str | None = None) -> dict:
        return await self.client.attach_media(
            {
                "source_path": source_path,
                "date": date,
                "original_name": original_name,
            }
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
    normalized = value.replace("，", ",").replace("、", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _brief_error(exc: Exception) -> str:
    if isinstance(exc, aiohttp.ClientResponseError):
        return f"HTTP {exc.status}: {exc.message}"
    return str(exc)


def _split_lines(value: str | None) -> list[str]:
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def _is_time_now(now: datetime, configured: str) -> bool:
    try:
        hour_text, minute_text = configured.strip().split(":", 1)
        return now.hour == int(hour_text) and now.minute == int(minute_text)
    except Exception:
        return False


@register(
    PLUGIN_NAME,
    "local",
    "连接独立小窝日记服务的 AstrBot 插件。",
    "0.1.6",
)
class NestDiaryConnectorPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        self.client = NestDiaryClient(
            service_url=self.config.get("service_url", "http://nest-diary:28080"),
            token=self.config.get("bot_api_token", ""),
            timeout_seconds=int(self.config.get("request_timeout_seconds", 30)),
        )
        self.tools = NestDiaryTools(self.client)
        self._last_daily_sent = ""
        self._last_reminder_sent = ""
        self._scheduler_task = None
        if self.config.get("scheduled_prompt_enabled", True):
            try:
                self._scheduler_task = asyncio.create_task(self._scheduled_prompt_loop())
            except RuntimeError:
                self._scheduler_task = None

    async def terminate(self):
        if self._scheduler_task:
            self._scheduler_task.cancel()

    @filter.command("小窝状态")
    async def nest_status(self, event: AstrMessageEvent):
        """检查小窝日记服务是否在线。"""
        try:
            status = await self.client.status()
            message = f"小窝在线：{status.get('status', 'unknown')}"
        except Exception as exc:
            message = f"小窝暂时连不上：{_brief_error(exc)}"
        yield event.plain_result(message)

    @filter.command("小窝绑定提醒")
    async def bind_nest_prompt_origin(self, event: AstrMessageEvent):
        """显示当前会话 origin，供管理员填入插件配置。"""
        yield event.plain_result(
            "把下面这一串填进插件配置 daily_target_origin，定时提示就会发到当前会话：\n"
            f"{event.unified_msg_origin}"
        )

    @filter.llm_tool(name="nest_status")
    async def nest_status_tool(self, event: AstrMessageEvent):
        """检查小窝日记服务是否在线。"""
        try:
            status = await self.client.status()
            message = f"小窝在线：{status.get('status', 'unknown')}"
        except Exception as exc:
            message = f"小窝暂时连不上：{_brief_error(exc)}"
        return message

    @filter.llm_tool(name="write_diary")
    async def write_diary_tool(
        self,
        event: AstrMessageEvent,
        date: str,
        body: str,
        mood: str = "",
        tags: str = "",
        people: str = "",
        media_refs: str = "",
        reason: str = "",
    ):
        """写入或更新某一天的小窝日记。

        Args:
            date(string): 日记日期，格式 YYYY-MM-DD。
            body(string): 日记正文，要包含 bot 自己的评价、感受和判断，不能只是流水账。
            mood(string): 情绪词，多个词用逗号分隔。
            tags(string): 标签，多个标签用逗号分隔。
            people(string): 相关人物，多个名字用逗号分隔。
            media_refs(string): 图片或媒体引用，每行一个 URL 或小窝媒体地址，可为空。
            reason(string): 写入原因，例如 nightly_archive、manual_update、memory整理。
        """
        try:
            result = await self.tools.write_diary(
                date=date,
                body=body,
                mood=_split_words(mood),
                tags=_split_words(tags),
                people=_split_words(people),
                media_refs=_split_lines(media_refs),
                reason=reason,
            )
            saved_date = result.get("date", date)
            revision = result.get("revision_id") or result.get("revision")
            suffix = f"，修订号：{revision}" if revision else ""
            message = f"已写入 {saved_date} 的小窝日记{suffix}。"
            if self.config.get("auto_impression_after_diary", True):
                prompt = self.config.get("impression_after_diary_prompt", "").strip()
                if prompt:
                    message = f"{message}\n\n人物印象自检提示：{prompt}"
        except Exception as exc:
            message = f"写入小窝日记失败：{_brief_error(exc)}"
        return message

    @filter.llm_tool(name="read_diary")
    async def read_diary_tool(self, event: AstrMessageEvent, date: str):
        """读取指定日期的小窝日记。

        Args:
            date(string): 要读取的日期，格式 YYYY-MM-DD。
        """
        try:
            result = await self.tools.read_diary(date)
            content = result.get("body") or result.get("content") or result.get("text") or ""
            if not content:
                message = f"{date} 没有找到日记。"
            else:
                message = f"{date} 的日记：\n{content}"
        except Exception as exc:
            message = f"读取小窝日记失败：{_brief_error(exc)}"
        return message

    @filter.llm_tool(name="search_diary")
    async def search_diary_tool(self, event: AstrMessageEvent, query: str, top_k: int = 8):
        """按关键词搜索小窝日记，避免一次性读取全部日记。

        Args:
            query(string): 搜索关键词、日期、人名、事件或情绪线索。
            top_k(number): 最多返回多少条结果，默认 8。
        """
        try:
            result = await self.tools.search_diary(query, top_k=int(top_k))
            items = result.get("items") or result.get("results") or []
            if not items:
                message = f"没有搜到和“{query}”相关的小窝日记。"
            else:
                lines = [f"搜到 {len(items)} 条和“{query}”相关的小窝日记："]
                for item in items:
                    item_date = item.get("date", "未知日期")
                    snippet = item.get("snippet") or item.get("summary") or item.get("body") or ""
                    lines.append(f"- {item_date}: {snippet}")
                message = "\n".join(lines)
        except Exception as exc:
            message = f"搜索小窝日记失败：{_brief_error(exc)}"
        return message

    @filter.llm_tool(name="attach_media")
    async def attach_media_tool(
        self,
        event: AstrMessageEvent,
        source_path: str,
        date: str,
        original_name: str = "",
    ):
        """把图片、语音或附件归档到指定日期的小窝媒体库。

        Args:
            source_path(string): AstrBot 容器内可访问的文件绝对路径。
            date(string): 归档到哪一天，格式 YYYY-MM-DD。
            original_name(string): 原始文件名，可为空。
        """
        try:
            result = await self.tools.attach_media(
                source_path=source_path,
                date=date,
                original_name=original_name or None,
            )
            asset = result.get("asset") or {}
            media_id = (
                asset.get("sha256")
                or asset.get("path")
                or result.get("media_id")
                or result.get("sha256")
                or result.get("path")
                or ""
            )
            message = f"已把媒体归档到 {date}。{media_id}"
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
        if self.config.get("daily_write_enabled", True):
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
                    lines.append(f"- {item.get('name', '未知')}: {item.get('summary', '')}")
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
            parts = [
                f"{item.get('name', name)} 的人物印象：",
                item.get("summary", ""),
            ]
            if item.get("traits"):
                parts.append("性格：" + "，".join(item["traits"]))
            if item.get("interests"):
                parts.append("兴趣：" + "，".join(item["interests"]))
            if item.get("preferences"):
                parts.append("偏好：" + "，".join(item["preferences"]))
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
            summary(string): 对这个人的稳定总结，应该基于可追溯证据。
            traits(string): 性格特征，多个词用逗号分隔。
            interests(string): 兴趣爱好，多个词用逗号分隔。
            preferences(string): 偏好或相处方式，多个词用逗号分隔。
            relationship(string): 与 bot 或项目的关系。
            evidence_dates(string): 支撑这次更新的日记日期，多个日期用逗号分隔。
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
