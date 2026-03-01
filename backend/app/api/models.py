from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.model import (
    AppendRequest,
    AIStatusOut,
    AIStopOut,
    CheckpointRequest,
    CurrentModelOut,
    AIStartOut,
    TimelineOut,
    WorkspaceDeleteOut,
    WorkspaceCreate,
    WorkspaceDetailOut,
    WorkspaceOut,
)
from app.services.model_service import (
    append_lines,
    create_checkpoint,
    create_workspace,
    delete_workspace,
    get_timeline,
    list_workspaces,
    read_current_model_text,
    safe_artifact_path,
    get_ai_status_for_workspace,
    stop_ai_run_for_workspace,
    start_ai_run_for_workspace,
    workspace_detail,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceOut)
def create_workspace_route(payload: WorkspaceCreate, db: Session = Depends(get_db)) -> WorkspaceOut:
    return create_workspace(db, payload.name)


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces_route(db: Session = Depends(get_db)) -> list[WorkspaceOut]:
    return list_workspaces(db)


@router.get("/{workspace_id}", response_model=WorkspaceDetailOut)
def get_workspace_route(workspace_id: str, db: Session = Depends(get_db)) -> WorkspaceDetailOut:
    workspace, latest_artifacts = workspace_detail(db, workspace_id)
    return WorkspaceDetailOut(workspace=workspace, latest_artifacts=latest_artifacts)


@router.post("/{workspace_id}/append")
def append_route(workspace_id: str, payload: AppendRequest, db: Session = Depends(get_db)):
    step, artifact = append_lines(db, workspace_id, payload.ldraw_lines, payload.message)
    return {"step": step, "artifact": artifact}


@router.post("/{workspace_id}/checkpoint")
def checkpoint_route(workspace_id: str, payload: CheckpointRequest, db: Session = Depends(get_db)):
    step, artifact = create_checkpoint(db, workspace_id, payload.message)
    return {"step": step, "artifact": artifact}


@router.get("/{workspace_id}/timeline", response_model=TimelineOut)
def timeline_route(workspace_id: str, db: Session = Depends(get_db)) -> TimelineOut:
    workspace, steps = get_timeline(db, workspace_id)
    return TimelineOut(workspace=workspace, steps=steps)


@router.get("/{workspace_id}/current", response_model=CurrentModelOut)
def current_route(workspace_id: str, db: Session = Depends(get_db)) -> CurrentModelOut:
    content = read_current_model_text(db, workspace_id)
    return CurrentModelOut(rel_path="model/current.ldr", content=content)


@router.get("/{workspace_id}/artifacts/{rel_path:path}")
def artifact_route(workspace_id: str, rel_path: str, db: Session = Depends(get_db)):
    path = safe_artifact_path(db, workspace_id, rel_path)
    if path.suffix.lower() in {".ldr", ".txt", ".json"}:
        return PlainTextResponse(path.read_text(encoding="utf-8", errors="ignore"))
    return FileResponse(path)


@router.delete("/{workspace_id}", response_model=WorkspaceDeleteOut)
def delete_workspace_route(workspace_id: str, db: Session = Depends(get_db)) -> WorkspaceDeleteOut:
    deleted_id, deleted = delete_workspace(db, workspace_id)
    return WorkspaceDeleteOut(id=deleted_id, deleted=deleted)


@router.post("/{workspace_id}/ai/run", response_model=AIStartOut)
async def start_ai_run_route(
    workspace_id: str,
    concept_image: UploadFile | None = File(None),
    run_name: str = Form(""),
    preset_path: str = Form("presets/bird_sculpt.json"),
    max_steps: int = Form(12),
    beam_width: int = Form(2),
    candidates_per_step: int = Form(3),
    score_threshold: float = Form(0.84),
    control_plane_url: str = Form("http://localhost:8000"),
    db: Session = Depends(get_db),
) -> AIStartOut:
    content = None
    concept_filename = None
    if concept_image is not None:
        content = await concept_image.read()
        if not content:
            raise HTTPException(status_code=400, detail="concept_image cannot be empty")
        concept_filename = concept_image.filename or "concept.png"
    result = start_ai_run_for_workspace(
        db=db,
        workspace_id=workspace_id,
        concept_filename=concept_filename,
        concept_bytes=content,
        run_name=run_name,
        preset_source_path=preset_path,
        max_steps=max_steps,
        beam_width=beam_width,
        candidates_per_step=candidates_per_step,
        score_threshold=score_threshold,
        control_plane_url=control_plane_url,
    )
    return AIStartOut(**result)


@router.get("/{workspace_id}/ai/status", response_model=AIStatusOut)
def ai_status_route(workspace_id: str, tail: int = 200, db: Session = Depends(get_db)) -> AIStatusOut:
    result = get_ai_status_for_workspace(db=db, workspace_id=workspace_id, tail=tail)
    return AIStatusOut(**result)


@router.post("/{workspace_id}/ai/stop", response_model=AIStopOut)
def stop_ai_route(workspace_id: str, db: Session = Depends(get_db)) -> AIStopOut:
    result = stop_ai_run_for_workspace(db=db, workspace_id=workspace_id)
    return AIStopOut(**result)

