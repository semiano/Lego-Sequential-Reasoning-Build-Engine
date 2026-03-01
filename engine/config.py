from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Resolution(BaseModel):
    w: int = 768
    h: int = 768


class Weights(BaseModel):
    concept_similarity: float = 0.55
    silhouette_similarity: float = 0.25
    complexity_penalty: float = 0.10
    progress_reward: float = 0.10


class LLMKnobs(BaseModel):
    temperature: float = 0.3
    max_tokens: int = 1200


class EnginePreset(BaseModel):
    subject: str = "lego sculpture"
    max_steps: int = 12
    beam_width: int = 2
    candidates_per_step: int = 3
    render_views: list[str] = Field(default_factory=lambda: ["iso"])
    turntable_frames: int = 0
    resolution: Resolution = Field(default_factory=Resolution)
    score_threshold: float = 0.84
    plateau_patience: int = 3
    weights: Weights = Field(default_factory=Weights)
    llm: LLMKnobs = Field(default_factory=LLMKnobs)


class EngineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    model_planner: str = "gpt-4.1"
    model_builder: str = "gpt-4.1-mini"
    model_namer: str = "gpt-4.1-mini"

    engine_data_dir: str = "data/engine"

    @property
    def resolved_engine_data_dir(self) -> Path:
        return Path(self.engine_data_dir).resolve()


def load_preset(preset_path: str) -> EnginePreset:
    payload = Path(preset_path).read_text(encoding="utf-8")
    return EnginePreset.model_validate_json(payload)


def get_settings() -> EngineSettings:
    return EngineSettings()
