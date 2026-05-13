from __future__ import annotations

from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register

from .client import NestDiaryClient
from .tools import NestDiaryTools


@register(
    "astrbot_plugin_nest_diary_connector",
    "local",
    "连接独立小窝日记服务的 AstrBot 插件。",
    "0.1.0",
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
