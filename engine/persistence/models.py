from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from engine.persistence.db import Base


class Run(Base):
    __tablename__ = "engine_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    concept_image: Mapped[str] = mapped_column(String(1024), nullable=False)
    knobs_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    inspiration_assets: Mapped[list["InspirationAsset"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    strategy_buckets: Mapped[list["StrategyBucket"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    steps: Mapped[list["Step"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class InspirationAsset(Base):
    __tablename__ = "inspiration_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("engine_runs.id"), nullable=False)
    image_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    run: Mapped[Run] = relationship(back_populates="inspiration_assets")


class StrategyBucket(Base):
    __tablename__ = "strategy_buckets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("engine_runs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exemplar_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    run: Mapped[Run] = relationship(back_populates="strategy_buckets")


class Step(Base):
    __tablename__ = "engine_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("engine_runs.id"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    run: Mapped[Run] = relationship(back_populates="steps")
    branches: Mapped[list["Branch"]] = relationship(back_populates="step", cascade="all, delete-orphan")


class Branch(Base):
    __tablename__ = "engine_branches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    step_id: Mapped[str] = mapped_column(String(36), ForeignKey("engine_steps.id"), nullable=False)
    score_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    step: Mapped[Step] = relationship(back_populates="branches")
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="branch", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "engine_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("engine_branches.id"), nullable=False)
    assembly_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scores_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    branch: Mapped[Branch] = relationship(back_populates="candidates")
