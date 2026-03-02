from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.render import RenderRequest, RenderResponse, RenderTempRequest, RenderTempResponse
from app.services.render_service import run_render, run_render_temp

router = APIRouter(prefix="/api/workspaces", tags=["renders"])


@router.post("/{workspace_id}/render", response_model=RenderResponse)
def render_workspace(workspace_id: str, payload: RenderRequest, db: Session = Depends(get_db)) -> RenderResponse:
    step_index, artifacts = run_render(
        db=db,
        workspace_id=workspace_id,
        views=payload.views,
        turntable_frames=payload.turntable_frames,
        w=payload.resolution.w,
        h=payload.resolution.h,
        message=payload.message,
    )
    return RenderResponse(step_index=step_index, artifacts=artifacts)


@router.post("/{workspace_id}/render_temp", response_model=RenderTempResponse)
def render_workspace_temp(workspace_id: str, payload: RenderTempRequest, db: Session = Depends(get_db)) -> RenderTempResponse:
    artifacts = run_render_temp(
        db=db,
        workspace_id=workspace_id,
        extra_lines=payload.extra_lines,
        views=payload.views,
        turntable_frames=payload.turntable_frames,
        w=payload.resolution.w,
        h=payload.resolution.h,
    )
    return RenderTempResponse(artifacts=artifacts)
