from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import json
import os
from collections import deque

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.db_models import Artifact, ArtifactType, ModelWorkspace, Step, StepKind
from app.core.ldraw import is_valid_ldraw_line
from app.core.storage import ensure_workspace_dirs, resolve_workspace_file_safe, workspace_root
from app.core.config import get_settings


def create_workspace(db: Session, name: str) -> ModelWorkspace:
    workspace = ModelWorkspace(name=name)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    ensure_workspace_dirs(workspace.id)
    return workspace


def list_workspaces(db: Session) -> list[ModelWorkspace]:
    stmt = select(ModelWorkspace).order_by(ModelWorkspace.created_at.desc())
    return list(db.scalars(stmt).all())


def get_workspace_or_404(db: Session, workspace_id: str) -> ModelWorkspace:
    workspace = db.get(ModelWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def _next_step(workspace: ModelWorkspace) -> int:
    return workspace.current_step + 1


def _step_rel_path(step_index: int) -> str:
    return f"model/step_{step_index:04d}.ldr"


def _create_artifact(db: Session, workspace_id: str, step_id: str, artifact_type: ArtifactType, rel_path: str) -> Artifact:
    artifact = Artifact(workspace_id=workspace_id, step_id=step_id, artifact_type=artifact_type, rel_path=rel_path)
    db.add(artifact)
    return artifact


def _write_snapshot(workspace_id: str, step_index: int) -> Path:
    root = ensure_workspace_dirs(workspace_id)
    current = root / "model" / "current.ldr"
    target = root / "model" / f"step_{step_index:04d}.ldr"
    target.write_text(current.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def append_lines(db: Session, workspace_id: str, ldraw_lines: list[str], message: str | None) -> tuple[Step, Artifact]:
    if not ldraw_lines:
        raise HTTPException(status_code=400, detail="ldraw_lines cannot be empty")
    for line in ldraw_lines:
        if not is_valid_ldraw_line(line):
            raise HTTPException(status_code=400, detail=f"Invalid LDraw line: {line}")

    workspace = get_workspace_or_404(db, workspace_id)
    root = ensure_workspace_dirs(workspace_id)
    current = root / "model" / "current.ldr"

    with current.open("a", encoding="utf-8") as handle:
        for line in ldraw_lines:
            handle.write(line.strip() + "\n")

    step_index = _next_step(workspace)
    snapshot = _write_snapshot(workspace_id, step_index)

    step = Step(
        workspace_id=workspace.id,
        step_index=step_index,
        kind=StepKind.append,
        message=message,
    )
    workspace.current_step = step_index
    workspace.updated_at = datetime.utcnow()
    db.add(step)
    db.flush()

    artifact = _create_artifact(db, workspace.id, step.id, ArtifactType.ldraw, str(snapshot.relative_to(root).as_posix()))
    db.commit()
    db.refresh(step)
    db.refresh(artifact)
    return step, artifact


def create_checkpoint(db: Session, workspace_id: str, message: str | None) -> tuple[Step, Artifact]:
    workspace = get_workspace_or_404(db, workspace_id)
    step_index = _next_step(workspace)
    snapshot = _write_snapshot(workspace_id, step_index)
    root = ensure_workspace_dirs(workspace_id)

    step = Step(
        workspace_id=workspace.id,
        step_index=step_index,
        kind=StepKind.checkpoint,
        message=message,
    )
    workspace.current_step = step_index
    workspace.updated_at = datetime.utcnow()
    db.add(step)
    db.flush()

    artifact = _create_artifact(db, workspace.id, step.id, ArtifactType.ldraw, str(snapshot.relative_to(root).as_posix()))
    db.commit()
    db.refresh(step)
    db.refresh(artifact)
    return step, artifact


def get_timeline(db: Session, workspace_id: str) -> tuple[ModelWorkspace, list[Step]]:
    workspace = get_workspace_or_404(db, workspace_id)
    stmt = (
        select(Step)
        .where(Step.workspace_id == workspace_id)
        .options(joinedload(Step.artifacts))
        .order_by(Step.step_index.asc())
    )
    steps = list(db.scalars(stmt).unique().all())
    return workspace, steps


def workspace_detail(db: Session, workspace_id: str) -> tuple[ModelWorkspace, list[Artifact]]:
    workspace = get_workspace_or_404(db, workspace_id)
    stmt = (
        select(Artifact)
        .where(Artifact.workspace_id == workspace_id)
        .order_by(Artifact.created_at.desc())
        .limit(12)
    )
    artifacts = list(db.scalars(stmt).all())
    return workspace, artifacts


def read_current_model_text(db: Session, workspace_id: str) -> str:
    get_workspace_or_404(db, workspace_id)
    root = ensure_workspace_dirs(workspace_id)
    return (root / "model" / "current.ldr").read_text(encoding="utf-8")


def safe_artifact_path(db: Session, workspace_id: str, rel_path: str) -> Path:
    get_workspace_or_404(db, workspace_id)
    try:
        path = resolve_workspace_file_safe(workspace_id, rel_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid artifact path") from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return path


def delete_workspace(db: Session, workspace_id: str) -> tuple[str, bool]:
    workspace = get_workspace_or_404(db, workspace_id)
    root = workspace_root(workspace_id)
    db.delete(workspace)
    db.commit()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    return workspace_id, True


def start_ai_run_for_workspace(
    db: Session,
    workspace_id: str,
    concept_filename: str,
    concept_bytes: bytes,
    run_name: str,
    preset_source_path: str,
    max_steps: int,
    beam_width: int,
    candidates_per_step: int,
    score_threshold: float,
    control_plane_url: str,
) -> dict:
    workspace = get_workspace_or_404(db, workspace_id)
    settings = get_settings()
    repo_root = settings.repo_root

    engine_root = (repo_root / "data" / "engine").resolve()
    concepts_dir = engine_root / "concepts"
    runtime_presets_dir = engine_root / "runtime_presets"
    runtime_state_dir = engine_root / "runtime"
    run_logs_dir = engine_root / "runs"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    runtime_presets_dir.mkdir(parents=True, exist_ok=True)
    runtime_state_dir.mkdir(parents=True, exist_ok=True)
    run_logs_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(concept_filename or "concept.png").suffix or ".png"
    concept_path = concepts_dir / f"{workspace_id}_{uuid.uuid4().hex[:8]}{suffix}"
    concept_path.write_bytes(concept_bytes)

    preset_path = (repo_root / preset_source_path).resolve()
    if not preset_path.exists():
        raise HTTPException(status_code=400, detail=f"Preset not found: {preset_source_path}")

    try:
        preset = json.loads(preset_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Preset JSON is invalid") from exc

    preset["max_steps"] = max_steps
    preset["beam_width"] = beam_width
    preset["candidates_per_step"] = candidates_per_step
    preset["score_threshold"] = score_threshold

    runtime_preset_path = runtime_presets_dir / f"{workspace_id}_{uuid.uuid4().hex[:8]}.json"
    runtime_preset_path.write_text(json.dumps(preset, indent=2), encoding="utf-8")

    command = [
        sys.executable,
        "-m",
        "engine.main",
        "run",
        "--concept",
        str(concept_path),
        "--name",
        run_name or workspace.name,
        "--workspace-id",
        workspace_id,
        "--control-plane",
        control_plane_url,
        "--preset",
        str(runtime_preset_path),
    ]

    log_path = run_logs_dir / f"workspace_{workspace_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.log"
    state_path = runtime_state_dir / f"{workspace_id}.json"

    log_handle = open(log_path, "a", encoding="utf-8")
    log_handle.write(f"[{datetime.utcnow().isoformat()}] Starting AI run for workspace {workspace_id}\n")
    log_handle.write(f"Command: {' '.join(command)}\n")
    log_handle.flush()

    process = subprocess.Popen(
        command,
        cwd=str(repo_root),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    log_handle.close()

    state_path.write_text(
        json.dumps(
            {
                "workspace_id": workspace_id,
                "pid": process.pid,
                "command": command,
                "started_at": datetime.utcnow().isoformat(),
                "concept_image_path": str(concept_path),
                "preset_path": str(runtime_preset_path),
                "log_path": str(log_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "workspace_id": workspace_id,
        "command": command,
        "concept_image_path": str(concept_path),
        "preset_path": str(runtime_preset_path),
        "pid": process.pid,
        "log_path": str(log_path),
    }


def _pid_is_running(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _tail_lines(path: Path, count: int) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return [line.rstrip("\n") for line in deque(handle, maxlen=max(1, count))]


def get_ai_status_for_workspace(db: Session, workspace_id: str, tail: int = 200) -> dict:
    get_workspace_or_404(db, workspace_id)
    settings = get_settings()
    state_path = settings.repo_root / "data" / "engine" / "runtime" / f"{workspace_id}.json"
    if not state_path.exists():
        return {
            "workspace_id": workspace_id,
            "running": False,
            "pid": None,
            "started_at": None,
            "concept_image_path": None,
            "preset_path": None,
            "log_path": None,
            "log_lines": [],
        }

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}

    pid = state.get("pid")
    running = _pid_is_running(pid if isinstance(pid, int) else None)
    log_path_value = state.get("log_path")
    log_path = Path(log_path_value) if isinstance(log_path_value, str) else None
    lines = _tail_lines(log_path, min(max(20, tail), 1000)) if log_path else []

    return {
        "workspace_id": workspace_id,
        "running": running,
        "pid": pid if isinstance(pid, int) else None,
        "started_at": state.get("started_at"),
        "concept_image_path": state.get("concept_image_path"),
        "preset_path": state.get("preset_path"),
        "log_path": str(log_path) if log_path else None,
        "log_lines": lines,
    }
