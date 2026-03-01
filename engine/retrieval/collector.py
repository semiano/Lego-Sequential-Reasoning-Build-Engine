from __future__ import annotations

from pathlib import Path
from typing import Any
import uuid

import httpx
import numpy as np
from sqlalchemy.orm import Session

from engine.evaluator.clip_embedder import ClipEmbedder
from engine.persistence.models import InspirationAsset
from engine.retrieval.search_provider import SearchProvider


class InspirationCollector:
    def __init__(self, search_provider: SearchProvider, embedder: ClipEmbedder, cache_dir: Path):
        self.search_provider = search_provider
        self.embedder = embedder
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def collect(
        self,
        db: Session,
        run_id: str,
        subject: str,
        min_assets: int = 30,
        max_assets: int = 80,
    ) -> list[InspirationAsset]:
        queries = [
            f"lego {subject} moc",
            f"lego {subject} sculpture",
            f"lego {subject} build",
        ]

        urls: list[str] = []
        for query in queries:
            results = await self.search_provider.search_images(query=query, limit=max_assets // len(queries) + 5)
            urls.extend(results)

        deduped = []
        seen = set()
        for url in urls:
            if url in seen:
                continue
            deduped.append(url)
            seen.add(url)
            if len(deduped) >= max_assets:
                break

        if len(deduped) < min_assets:
            deduped = deduped + deduped[: max(0, min_assets - len(deduped))]

        saved_assets: list[InspirationAsset] = []
        for index, url in enumerate(deduped[:max_assets]):
            local_path = self.cache_dir / f"{run_id}_{index:03d}_{uuid.uuid4().hex[:8]}.img"
            ok = await self._download_image(url, local_path)
            if not ok:
                continue
            embedding = self.embedder.embed_image(local_path)
            record = InspirationAsset(
                run_id=run_id,
                image_url=url,
                embedding=np.array2string(embedding, separator=",", max_line_width=10_000),
                metadata_json={"local_path": str(local_path)},
            )
            db.add(record)
            saved_assets.append(record)

        db.commit()
        for item in saved_assets:
            db.refresh(item)
        return saved_assets

    async def _download_image(self, url: str, path: Path) -> bool:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            path.write_bytes(response.content)
            return True
        except Exception:
            return False
