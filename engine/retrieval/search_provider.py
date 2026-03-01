from __future__ import annotations

from abc import ABC, abstractmethod


class SearchProvider(ABC):
    @abstractmethod
    async def search_images(self, query: str, limit: int) -> list[str]:
        raise NotImplementedError
