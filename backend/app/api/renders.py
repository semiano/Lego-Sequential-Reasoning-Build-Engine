from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.render import RenderRequest, RenderResponse
from app.services.render_service import run_render

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
