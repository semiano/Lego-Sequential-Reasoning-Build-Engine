from __future__ import annotations

from statistics import mean

from engine.builder.ldraw_converter import parse_type1_line


def _bbox_center(bbox: dict) -> dict[str, float]:
    return {
        "x": (bbox["min_x"] + bbox["max_x"]) / 2.0,
        "y": (bbox["min_y"] + bbox["max_y"]) / 2.0,
        "z": (bbox["min_z"] + bbox["max_z"]) / 2.0,
    }


def _parse_type1_lines(ldraw_text: str) -> list[dict]:
    parsed: list[dict] = []
    for line in ldraw_text.splitlines():
        item = parse_type1_line(line)
        if item:
            parsed.append(item)
    return parsed


def _line_signature(parsed: dict) -> str:
    position = parsed["position"]
    matrix = parsed["matrix"]
    matrix_sig = ",".join(f"{float(v):.4f}" for v in matrix)
    return (
        f"{parsed['part_id']}|{parsed['color']}|"
        f"{float(position['x']):.4f},{float(position['y']):.4f},{float(position['z']):.4f}|{matrix_sig}"
    )


def _compute_bbox(parsed_lines: list[dict]) -> dict:
    if not parsed_lines:
        return {
            "min_x": 0.0,
            "max_x": 0.0,
            "min_y": 0.0,
            "max_y": 0.0,
            "min_z": 0.0,
            "max_z": 0.0,
        }

    xs = [item["position"]["x"] for item in parsed_lines]
    ys = [item["position"]["y"] for item in parsed_lines]
    zs = [item["position"]["z"] for item in parsed_lines]
    return {
        "min_x": float(min(xs)),
        "max_x": float(max(xs)),
        "min_y": float(min(ys)),
        "max_y": float(max(ys)),
        "min_z": float(min(zs)),
        "max_z": float(max(zs)),
    }


async def summarize_model_state(
    current_model_text: str,
    timeline: dict,
    fetch_artifact_text,
    recent_limit: int = 20,
) -> dict:
    parsed_current = _parse_type1_lines(current_model_text)
    bbox = _compute_bbox(parsed_current)

    current_lines = [line.strip() for line in current_model_text.splitlines() if line.strip()]
    recent_lines = current_lines[-max(1, recent_limit) :]

    last_append_step = None
    steps = timeline.get("steps", [])
    for step in reversed(steps):
        if step.get("kind") == "append":
            last_append_step = step
            break

    appended_positions: list[tuple[float, float, float]] = []
    recent_additions: list[str] = recent_lines[-max(1, recent_limit) :]

    if last_append_step:
        last_step_index = int(last_append_step.get("step_index", 0))
        last_snapshot_rel = None
        for artifact in last_append_step.get("artifacts", []):
            if artifact.get("artifact_type") == "ldraw":
                last_snapshot_rel = artifact.get("rel_path")
                break

        prev_snapshot_rel = None
        for step in reversed(steps):
            if int(step.get("step_index", 0)) >= last_step_index:
                continue
            for artifact in step.get("artifacts", []):
                if artifact.get("artifact_type") == "ldraw":
                    prev_snapshot_rel = artifact.get("rel_path")
                    break
            if prev_snapshot_rel:
                break

        if last_snapshot_rel:
            last_text = await fetch_artifact_text(str(last_snapshot_rel))
            prev_text = await fetch_artifact_text(str(prev_snapshot_rel)) if prev_snapshot_rel else ""

            last_parsed = _parse_type1_lines(last_text)
            prev_sigs = {_line_signature(item) for item in _parse_type1_lines(prev_text)}
            diff_items = [item for item in last_parsed if _line_signature(item) not in prev_sigs]

            if diff_items:
                appended_positions = [
                    (float(item["position"]["x"]), float(item["position"]["y"]), float(item["position"]["z"]))
                    for item in diff_items
                ]
                diff_lines = [line for line in last_text.splitlines() if parse_type1_line(line)]
                recent_additions = diff_lines[-max(1, recent_limit) :]

    if appended_positions:
        anchor = {
            "x": float(mean([pos[0] for pos in appended_positions])),
            "y": float(mean([pos[1] for pos in appended_positions])),
            "z": float(mean([pos[2] for pos in appended_positions])),
        }
    else:
        anchor = _bbox_center(bbox)

    return {
        "bbox": bbox,
        "anchor": anchor,
        "part_count": len(parsed_current),
        "recent_lines": recent_lines,
        "recent_additions": recent_additions,
    }
