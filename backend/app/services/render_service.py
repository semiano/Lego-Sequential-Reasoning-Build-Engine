from datetime import datetime
from pathlib import Path
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.db_models import Artifact, ArtifactType, Step, StepKind
from app.core.leocad_cli import LeoCADCLI, LeoCADError
from app.core.storage import ensure_workspace_dirs
from app.services.model_service import _create_artifact, _next_step, _write_snapshot, get_workspace_or_404


def _render_snapshot_to_outputs(
    snapshot: Path,
    out_dir: Path,
    views: list[str],
    turntable_frames: int,
    w: int,
    h: int,
) -> tuple[list[Path], list[Path]]:
    cli = LeoCADCLI()
    turntable_dir = out_dir / "turntable"
    view_outputs = cli.render_views(snapshot, out_dir, views, w, h)
    turntable_outputs = cli.render_turntable(snapshot, turntable_dir, turntable_frames, w, h)
    return view_outputs, turntable_outputs


def run_render(
    db: Session,
    workspace_id: str,
    views: list[str],
    turntable_frames: int,
    w: int,
    h: int,
    message: str | None,
) -> tuple[int, list[Artifact]]:
    workspace = get_workspace_or_404(db, workspace_id)
    if not views:
        views = ["iso"]

    step_index = _next_step(workspace)
    root = ensure_workspace_dirs(workspace_id)
    snapshot = _write_snapshot(workspace_id, step_index)
    out_dir = root / "renders" / f"step_{step_index:04d}"
    turntable_dir = out_dir / "turntable"

    step = Step(
        workspace_id=workspace.id,
        step_index=step_index,
        kind=StepKind.render,
        message=message,
    )
    workspace.current_step = step_index
    workspace.updated_at = datetime.utcnow()
    db.add(step)
    db.flush()

    created: list[Artifact] = []
    created.append(_create_artifact(db, workspace.id, step.id, ArtifactType.ldraw, str(snapshot.relative_to(root).as_posix())))

    try:
        view_outputs, turntable_outputs = _render_snapshot_to_outputs(
            snapshot=snapshot,
            out_dir=out_dir,
            views=views,
            turntable_frames=turntable_frames,
            w=w,
            h=h,
        )
    except LeoCADError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Render failed: {exc}") from exc

    for item in view_outputs:
        created.append(
            _create_artifact(db, workspace.id, step.id, ArtifactType.render, str(item.relative_to(root).as_posix()))
        )

    for item in turntable_outputs:
        created.append(
            _create_artifact(db, workspace.id, step.id, ArtifactType.turntable_frame, str(item.relative_to(root).as_posix()))
        )

    db.commit()
    for artifact in created:
        db.refresh(artifact)
    return step_index, created


def run_render_temp(
    db: Session,
    workspace_id: str,
    extra_lines: list[str],
    views: list[str],
    turntable_frames: int,
    w: int,
    h: int,
) -> list[dict[str, str]]:
    get_workspace_or_404(db, workspace_id)
    root = ensure_workspace_dirs(workspace_id)
    if not views:
        views = ["iso"]

    current_path = root / "model" / "current.ldr"
    temp_token = uuid.uuid4().hex[:8]
    temp_dir = root / "renders" / "temp" / temp_token
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_model_path = temp_dir / "temp.ldr"

    current_text = current_path.read_text(encoding="utf-8")
    merged_lines = [line.rstrip("\n") for line in current_text.splitlines() if line.strip()]
    merged_lines.extend([line.rstrip("\n") for line in extra_lines if str(line).strip()])
    temp_model_path.write_text("\n".join(merged_lines) + "\n", encoding="utf-8")

    try:
        view_outputs, turntable_outputs = _render_snapshot_to_outputs(
            snapshot=temp_model_path,
            out_dir=temp_dir,
            views=views,
            turntable_frames=turntable_frames,
            w=w,
            h=h,
        )
    except LeoCADError as exc:
        raise HTTPException(status_code=500, detail=f"Temp render failed: {exc}") from exc

    artifacts: list[dict[str, str]] = []
    for item in view_outputs:
        artifacts.append({"artifact_type": "render", "rel_path": str(item.relative_to(root).as_posix())})
    for item in turntable_outputs:
        artifacts.append({"artifact_type": "turntable_frame", "rel_path": str(item.relative_to(root).as_posix())})

    return artifacts
