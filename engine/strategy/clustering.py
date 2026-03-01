from __future__ import annotations

import ast
import numpy as np

from engine.persistence.models import InspirationAsset


def _parse_embedding(raw: str) -> np.ndarray:
    values = ast.literal_eval(raw)
    if isinstance(values, (list, tuple)):
        return np.array(values, dtype=np.float32)
    return np.array([0.0, 0.0, 0.0], dtype=np.float32)


def kmeans_cluster_assets(assets: list[InspirationAsset], k: int) -> dict[int, list[InspirationAsset]]:
    if not assets:
        return {}

    vectors = np.vstack([_parse_embedding(asset.embedding) for asset in assets])
    k = max(1, min(k, len(assets)))
    centroids = vectors[:k].copy()

    for _ in range(10):
        distances = np.linalg.norm(vectors[:, None, :] - centroids[None, :, :], axis=2)
        labels = distances.argmin(axis=1)
        for idx in range(k):
            members = vectors[labels == idx]
            if len(members) > 0:
                centroids[idx] = members.mean(axis=0)

    buckets: dict[int, list[InspirationAsset]] = {idx: [] for idx in range(k)}
    for asset, label in zip(assets, labels):
        buckets[int(label)].append(asset)
    return buckets
