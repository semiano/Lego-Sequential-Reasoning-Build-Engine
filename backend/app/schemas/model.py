from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class WorkspaceOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    current_step: int
    desired_image_rel_path: str | None = None

    model_config = {"from_attributes": True}


class ArtifactOut(BaseModel):
    id: str
    artifact_type: str
    rel_path: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StepOut(BaseModel):
    id: str
    step_index: int
    kind: Literal["append", "render", "checkpoint"]
    message: str | None
    created_at: datetime
    artifacts: list[ArtifactOut] = []

    model_config = {"from_attributes": True}


class WorkspaceDetailOut(BaseModel):
    workspace: WorkspaceOut
    latest_artifacts: list[ArtifactOut]


class AppendRequest(BaseModel):
    ldraw_lines: list[str]
    message: str | None = None


class CheckpointRequest(BaseModel):
    message: str | None = None


class TimelineOut(BaseModel):
    workspace: WorkspaceOut
    steps: list[StepOut]


class CurrentModelOut(BaseModel):
    rel_path: str
    content: str


class WorkspaceDeleteOut(BaseModel):
    id: str
    deleted: bool


class AIStartOut(BaseModel):
    workspace_id: str
    command: list[str]
    concept_image_path: str
    preset_path: str
    pid: int
    log_path: str


class AIStatusOut(BaseModel):
    workspace_id: str
    running: bool
    pid: int | None
    started_at: str | None
    concept_image_path: str | None
    preset_path: str | None
    log_path: str | None
    log_lines: list[str]


class AIStopOut(BaseModel):
    workspace_id: str
    stopped: bool
    pid: int | None
    message: str
