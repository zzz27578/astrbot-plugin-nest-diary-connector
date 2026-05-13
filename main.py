from __future__ import annotations

import aiohttp
from astrbot.api.event import AstrMessageEvent, filter
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
        reason: str = "",
    ) -> dict:
        return await self.client.write_diary(
            {
                "date": date,
                "body": body,
                "mood": mood or [],
                "tags": tags or [],
                "people": people or [],
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


def _split_words(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace("，", ",").replace("、", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _brief_error(exc: Exception) -> str:
    if isinstance(exc, aiohttp.ClientResponseError):
        return f"HTTP {exc.status}: {exc.message}"
    return str(exc)


@register(
    PLUGIN_NAME,
    "local",
    "连接独立小窝日记服务的 AstrBot 插件。",
    "0.1.4",
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

    @filter.command("小窝状态")
    async def nest_status(self, event: AstrMessageEvent):
        """检查小窝日记服务是否在线。"""
        try:
            status = await self.client.status()
            message = f"小窝在线：{status.get('status', 'unknown')}"
        except Exception as exc:
            message = f"小窝暂时连不上：{_brief_error(exc)}"
        yield event.plain_result(message)

    @filter.llm_tool(name="nest_status")
    async def nest_status_tool(self, event: AstrMessageEvent):
        """检查小窝日记服务是否在线。"""
        try:
            status = await self.client.status()
            message = f"小窝在线：{status.get('status', 'unknown')}"
        except Exception as exc:
            message = f"小窝暂时连不上：{_brief_error(exc)}"
        yield event.plain_result(message)

    @filter.llm_tool(name="write_diary")
    async def write_diary_tool(
        self,
        event: AstrMessageEvent,
        date: str,
        body: str,
        mood: str = "",
        tags: str = "",
        people: str = "",
        reason: str = "",
    ):
        """写入或更新某一天的小窝日记。

        Args:
            date(string): 日记日期，格式 YYYY-MM-DD。
            body(string): 日记正文，要包含 bot 自己的评价、感受和判断，不能只是流水账。
            mood(string): 情绪词，多个词用逗号分隔。
            tags(string): 标签，多个标签用逗号分隔。
            people(string): 相关人物，多个名字用逗号分隔。
            reason(string): 写入原因，例如 nightly_archive、manual_update、memory整理。
        """
        try:
            result = await self.tools.write_diary(
                date=date,
                body=body,
                mood=_split_words(mood),
                tags=_split_words(tags),
                people=_split_words(people),
                reason=reason,
            )
            saved_date = result.get("date", date)
            revision = result.get("revision_id") or result.get("revision")
            suffix = f"，修订号：{revision}" if revision else ""
            message = f"已写入 {saved_date} 的小窝日记{suffix}。"
        except Exception as exc:
            message = f"写入小窝日记失败：{_brief_error(exc)}"
        yield event.plain_result(message)

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
        yield event.plain_result(message)

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
        yield event.plain_result(message)

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
        yield event.plain_result(message)
