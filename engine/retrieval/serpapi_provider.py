from __future__ import annotations

import os

import httpx

from engine.retrieval.search_provider import SearchProvider


class SerpApiProvider(SearchProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")

    async def search_images(self, query: str, limit: int) -> list[str]:
        if not self.api_key:
            return []

        params = {
            "engine": "google_images",
            "q": query,
            "api_key": self.api_key,
            "ijn": "0",
        }
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.get("https://serpapi.com/search.json", params=params)
            response.raise_for_status()
            payload = response.json()

        images = payload.get("images_results", [])
        urls: list[str] = []
        for item in images:
            url = item.get("original") or item.get("thumbnail")
            if url:
                urls.append(url)
            if len(urls) >= limit:
                break
        return urls
