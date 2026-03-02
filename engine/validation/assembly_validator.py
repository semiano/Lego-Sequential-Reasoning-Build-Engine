from __future__ import annotations

import math

from engine.builder.ldraw_converter import normalized_type1_key


def _snap(value: float, unit: float) -> float:
    if unit == 0:
        return value
    return round(value / unit) * unit


def _distance(a: dict, b: dict) -> float:
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)


def _is_axis_aligned_matrix(matrix: list[float]) -> bool:
    if len(matrix) != 9:
        return False
    rounded = []
    for value in matrix:
        nearest = round(value)
        if abs(value - nearest) > 1e-3:
            return False
        rounded.append(int(nearest))

    allowed = {-1, 0, 1}
    if any(value not in allowed for value in rounded):
        return False

    rows = [rounded[0:3], rounded[3:6], rounded[6:9]]
    cols = [
        [rows[0][0], rows[1][0], rows[2][0]],
        [rows[0][1], rows[1][1], rows[2][1]],
        [rows[0][2], rows[1][2], rows[2][2]],
    ]

    def unit_axis(vec: list[int]) -> bool:
        return sum(abs(v) for v in vec) == 1

    return all(unit_axis(row) for row in rows) and all(unit_axis(col) for col in cols)


def _in_expanded_bbox(position: dict, bbox: dict, margin: float) -> bool:
    return (
        bbox["min_x"] - margin <= position["x"] <= bbox["max_x"] + margin
        and bbox["min_y"] - margin <= position["y"] <= bbox["max_y"] + margin
        and bbox["min_z"] - margin <= position["z"] <= bbox["max_z"] + margin
    )


def validate_and_normalize(
    assembly_json: dict,
    bbox: dict,
    anchor: dict,
    rules: dict,
    existing_lines_hashset: set[str],
) -> tuple[bool, dict, list[str]]:
    errors: list[str] = []

    xz_unit = float(rules.get("xz_unit", 20))
    y_unit = float(rules.get("y_unit", 8))
    snap_mode = str(rules.get("snap_mode", "snap")).lower()
    snap_epsilon = float(rules.get("snap_epsilon", 0.01))
    bbox_margin = float(rules.get("bbox_margin", 80.0))
    anchor_radius = float(rules.get("anchor_radius", 120.0))
    require_axis = bool(rules.get("require_axis_aligned_matrix", True))

    assemblies = assembly_json.get("assemblies", [])
    normalized_assemblies: list[dict] = []

    has_connected = False

    for index, item in enumerate(assemblies):
        part_id = str(item.get("part_id", "")).strip()
        matrix = [float(value) for value in item.get("matrix", [])]
        position = {
            "x": float(item.get("position", {}).get("x", 0.0)),
            "y": float(item.get("position", {}).get("y", 0.0)),
            "z": float(item.get("position", {}).get("z", 0.0)),
        }

        snapped = {
            "x": _snap(position["x"], xz_unit),
            "y": _snap(position["y"], y_unit),
            "z": _snap(position["z"], xz_unit),
        }

        for axis in ("x", "y", "z"):
            if abs(position[axis] - snapped[axis]) > snap_epsilon:
                if snap_mode == "reject":
                    errors.append(f"assemblies[{index}] off-grid on {axis}: {position[axis]} (unit rule violation)")
                position[axis] = snapped[axis]
            else:
                position[axis] = snapped[axis]

        if require_axis and not _is_axis_aligned_matrix(matrix):
            errors.append(f"assemblies[{index}] matrix is not axis-aligned 90-degree rotation")

        in_bbox = _in_expanded_bbox(position, bbox, bbox_margin)
        near_anchor = _distance(position, anchor) <= anchor_radius

        if not (in_bbox or near_anchor):
            errors.append(f"assemblies[{index}] too far from current structure/anchor")

        if in_bbox and near_anchor:
            has_connected = True

        key = normalized_type1_key(part_id=part_id, position=position, matrix=matrix)
        if key in existing_lines_hashset:
            errors.append(f"assemblies[{index}] duplicates an existing placement")

        normalized_assemblies.append(
            {
                **item,
                "position": {
                    "x": position["x"],
                    "y": position["y"],
                    "z": position["z"],
                },
                "matrix": matrix,
                "part_id": part_id,
            }
        )

    if normalized_assemblies and not has_connected:
        errors.append("No connected placement found near anchor and within expanded bbox")

    ok = len(errors) == 0
    normalized_json = {**assembly_json, "assemblies": normalized_assemblies}
    return ok, normalized_json, errors
