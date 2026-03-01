from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.schemas.parts import PartDetailOut
from app.services.parts_service import get_part_detail, render_part_preview, search_parts

router = APIRouter(prefix="/api/parts", tags=["parts"])


@router.get("/search", response_model=list[str])
def part_search(q: str = Query("", min_length=1), limit: int = Query(25, ge=1, le=200)) -> list[str]:
    return search_parts(query=q, limit=limit)


@router.get("/{part_id}", response_model=PartDetailOut)
def part_detail(part_id: str) -> PartDetailOut:
    return PartDetailOut(**get_part_detail(part_id))


@router.get("/{part_id}/preview")
def part_preview(
    part_id: str,
    view: str = "iso",
    w: int = Query(512, ge=64, le=4096),
    h: int = Query(512, ge=64, le=4096),
):
    out_path = render_part_preview(part_id=part_id, view=view, w=w, h=h)
    return FileResponse(out_path)
