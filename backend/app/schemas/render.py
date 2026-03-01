from pydantic import BaseModel, Field

from app.schemas.model import ArtifactOut


class RenderResolution(BaseModel):
    w: int = Field(default=1024, ge=64, le=8192)
    h: int = Field(default=1024, ge=64, le=8192)


class RenderRequest(BaseModel):
    views: list[str] = Field(default_factory=lambda: ["iso"])
    turntable_frames: int = Field(default=0, ge=0, le=360)
    resolution: RenderResolution = Field(default_factory=RenderResolution)
    message: str | None = None


class RenderResponse(BaseModel):
    step_index: int
    artifacts: list[ArtifactOut]
