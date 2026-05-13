from __future__ import annotations

import aiohttp
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register


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


@register(
    "astrbot_plugin_nest_diary_connector",
    "local",
    "连接独立小窝日记服务的 AstrBot 插件。",
    "0.1.1",
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
    async def nest_status(self, event):
        try:
            status = await self.client.status()
            message = f"小窝在线：{status.get('status', 'unknown')}"
        except Exception as exc:
            message = f"小窝暂时连不上：{exc}"
        yield event.plain_result(message)
