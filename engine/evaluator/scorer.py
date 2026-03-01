from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from engine.evaluator.clip_embedder import ClipEmbedder


class LocalScorer:
    def __init__(self, embedder: ClipEmbedder, weights: dict[str, float]):
        self.embedder = embedder
        self.weights = weights

    def score(self, concept_image: Path, render_image: Path, part_count: int, step_index: int) -> dict:
        concept_emb = self.embedder.embed_image(concept_image)
        render_emb = self.embedder.embed_image(render_image)
        concept_similarity = self.embedder.cosine_similarity(concept_emb, render_emb)

        silhouette_similarity = self._silhouette_similarity(concept_image, render_image)
        complexity_penalty = min(1.0, part_count / 250.0)
        progress_reward = min(1.0, step_index / 20.0)

        score_total = (
            self.weights.get("concept_similarity", 0.55) * concept_similarity
            + self.weights.get("silhouette_similarity", 0.25) * silhouette_similarity
            - self.weights.get("complexity_penalty", 0.10) * complexity_penalty
            + self.weights.get("progress_reward", 0.10) * progress_reward
        )

        return {
            "concept_similarity": concept_similarity,
            "silhouette_similarity": silhouette_similarity,
            "complexity_penalty": complexity_penalty,
            "progress_reward": progress_reward,
            "score_total": score_total,
        }

    @staticmethod
    def _silhouette_similarity(concept_image: Path, render_image: Path) -> float:
        c = Image.open(concept_image).convert("L").resize((256, 256)).filter(ImageFilter.FIND_EDGES)
        r = Image.open(render_image).convert("L").resize((256, 256)).filter(ImageFilter.FIND_EDGES)
        ca = np.asarray(c, dtype=np.float32) / 255.0
        ra = np.asarray(r, dtype=np.float32) / 255.0
        diff = np.abs(ca - ra).mean()
        return float(max(0.0, 1.0 - diff))
