from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import HTTPException

from app.core.config import get_settings
from app.core.leocad_cli import LeoCADCLI, LeoCADError


def _sanitize_part_id(part_id: str) -> str:
    if "/" in part_id or "\\" in part_id or ".." in part_id:
        raise HTTPException(status_code=400, detail="Invalid part id")
    return part_id


def _find_part_file(part_id: str) -> Path | None:
    settings = get_settings()
    if not settings.ldraw_parts_dir:
        return None
    root = Path(settings.ldraw_parts_dir)
    candidate = part_id.lower()
    for dirpath, _dirnames, filenames in __import__("os").walk(root):
        for filename in filenames:
            if filename.lower() == candidate:
                return Path(dirpath) / filename
    return None


def search_parts(query: str, limit: int = 25) -> list[str]:
    settings = get_settings()
    if not settings.ldraw_parts_dir:
        return []
    root = Path(settings.ldraw_parts_dir)
    q = query.lower().strip()
    if not q:
        return []

    matches: list[str] = []
    for dirpath, _dirnames, filenames in __import__("os").walk(root):
        for filename in filenames:
            low = filename.lower()
            if not low.endswith(".dat"):
                continue
            if q in low:
                matches.append(filename)
                if len(matches) >= limit:
                    return sorted(set(matches))[:limit]
    return sorted(set(matches))[:limit]


def get_part_detail(part_id: str) -> dict:
    part_id = _sanitize_part_id(part_id)
    path = _find_part_file(part_id)
    if path is None:
        return {
            "part_id": part_id,
            "name": None,
            "raw_header": None,
            "file_path": None,
            "exists": False,
        }

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_lines: list[str] = []
    name: str | None = None
    for line in lines[:20]:
        if not line.startswith("0"):
            break
        header_lines.append(line)
        if line.lower().startswith("0 name:"):
            name = line.split(":", 1)[1].strip()

    return {
        "part_id": part_id,
        "name": name,
        "raw_header": "\n".join(header_lines),
        "file_path": str(path),
        "exists": True,
    }


def render_part_preview(part_id: str, view: str, w: int, h: int) -> Path:
    part_id = _sanitize_part_id(part_id)
    detail = get_part_detail(part_id)
    if not detail["exists"]:
        raise HTTPException(status_code=404, detail="Part not found")

    with NamedTemporaryFile("w", suffix=".ldr", delete=False, encoding="utf-8") as temp_ldr:
        temp_ldr.write("0 Part preview\n")
        temp_ldr.write(f"1 16 0 0 0 1 0 0 0 1 0 0 0 1 {part_id}\n")
        ldr_path = Path(temp_ldr.name)

    out_path = ldr_path.with_suffix(".png")
    cli = LeoCADCLI()
    try:
        cli.render_single(ldr_path, out_path, view or "iso", w, h)
    except LeoCADError as exc:
        raise HTTPException(status_code=500, detail=f"Preview render failed: {exc}") from exc
    return out_path
