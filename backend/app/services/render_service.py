from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.db_models import Artifact, ArtifactType, Step, StepKind
from app.core.leocad_cli import LeoCADCLI, LeoCADError
from app.core.storage import ensure_workspace_dirs
from app.services.model_service import _create_artifact, _next_step, _write_snapshot, get_workspace_or_404


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

    cli = LeoCADCLI()
    try:
        view_outputs = cli.render_views(snapshot, out_dir, views, w, h)
        turntable_outputs = cli.render_turntable(snapshot, turntable_dir, turntable_frames, w, h)
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
