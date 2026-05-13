from __future__ import annotations

from .client import NestDiaryClient


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
