import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class StepKind(str, Enum):
    append = "append"
    render = "render"
    checkpoint = "checkpoint"


class ArtifactType(str, Enum):
    ldraw = "ldraw"
    render = "render"
    turntable_frame = "turntable_frame"
    json = "json"


class ModelWorkspace(Base):
    __tablename__ = "model_workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    steps: Mapped[list["Step"]] = relationship("Step", back_populates="workspace", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship("Artifact", back_populates="workspace", cascade="all, delete-orphan")


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("model_workspaces.id"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[StepKind] = mapped_column(SAEnum(StepKind), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    workspace: Mapped[ModelWorkspace] = relationship("ModelWorkspace", back_populates="steps")
    artifacts: Mapped[list["Artifact"]] = relationship("Artifact", back_populates="step", cascade="all, delete-orphan")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("model_workspaces.id"), nullable=False)
    step_id: Mapped[str] = mapped_column(String(36), ForeignKey("steps.id"), nullable=False)
    artifact_type: Mapped[ArtifactType] = mapped_column(SAEnum(ArtifactType), nullable=False)
    rel_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    workspace: Mapped[ModelWorkspace] = relationship("ModelWorkspace", back_populates="artifacts")
    step: Mapped[Step] = relationship("Step", back_populates="artifacts")
