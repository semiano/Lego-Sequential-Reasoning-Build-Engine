from __future__ import annotations

from pathlib import Path
import importlib

import numpy as np
from PIL import Image


class ClipEmbedder:
    def __init__(self):
        self._clip_model = None
        self._clip_preprocess = None
        self._device = "cpu"
        self._fallback = True
        self._init_clip_if_available()

    def _init_clip_if_available(self) -> None:
        try:
            torch = importlib.import_module("torch")
            open_clip = importlib.import_module("open_clip")

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._clip_model, _, self._clip_preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained="laion2b_s34b_b79k"
            )
            self._clip_model = self._clip_model.to(self._device)
            self._clip_model.eval()
            self._fallback = False
        except Exception:
            self._fallback = True

    def embed_image(self, image_path: Path) -> np.ndarray:
        if self._fallback:
            return self._fallback_embed(image_path)

        try:
            torch = importlib.import_module("torch")

            image = Image.open(image_path).convert("RGB")
            tensor = self._clip_preprocess(image).unsqueeze(0).to(self._device)
            with torch.no_grad():
                features = self._clip_model.encode_image(tensor)
                features = features / features.norm(dim=-1, keepdim=True)
            return features[0].detach().cpu().numpy().astype(np.float32)
        except Exception:
            return self._fallback_embed(image_path)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom <= 1e-8:
            return 0.0
        return float(np.dot(a, b) / denom)

    @staticmethod
    def _fallback_embed(image_path: Path) -> np.ndarray:
        image = Image.open(image_path).convert("RGB").resize((64, 64))
        array = np.asarray(image, dtype=np.float32) / 255.0
        vector = array.mean(axis=(0, 1))
        return vector.astype(np.float32)
