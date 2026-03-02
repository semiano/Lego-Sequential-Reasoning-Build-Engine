from __future__ import annotations


def _norm_num(value: float) -> float:
    rounded = round(float(value), 4)
    return 0.0 if abs(rounded) < 1e-8 else rounded


def parse_type1_line(line: str) -> dict | None:
    parts = line.strip().split()
    if len(parts) < 15 or parts[0] != "1":
        return None
    try:
        color = int(float(parts[1]))
        x, y, z = (float(parts[2]), float(parts[3]), float(parts[4]))
        matrix = [float(value) for value in parts[5:14]]
        part_id = parts[14]
    except ValueError:
        return None
    return {
        "color": color,
        "position": {"x": x, "y": y, "z": z},
        "matrix": matrix,
        "part_id": part_id,
    }


def normalized_type1_key(part_id: str, position: dict, matrix: list[float]) -> str:
    matrix_str = ",".join(f"{_norm_num(value):g}" for value in matrix)
    return (
        f"{part_id}|"
        f"{_norm_num(position['x']):g},{_norm_num(position['y']):g},{_norm_num(position['z']):g}|"
        f"{matrix_str}"
    )


def normalized_type1_key_from_line(line: str) -> str | None:
    parsed = parse_type1_line(line)
    if not parsed:
        return None
    return normalized_type1_key(parsed["part_id"], parsed["position"], parsed["matrix"])


def existing_type1_hashset(ldraw_text: str) -> set[str]:
    output: set[str] = set()
    for line in ldraw_text.splitlines():
        key = normalized_type1_key_from_line(line)
        if key:
            output.add(key)
    return output


def assembly_to_ldraw_lines(assembly_json: dict) -> list[str]:
    lines: list[str] = []
    for item in assembly_json.get("assemblies", []):
        color = int(item["color"])
        x = float(item["position"]["x"])
        y = float(item["position"]["y"])
        z = float(item["position"]["z"])
        matrix = [float(v) for v in item["matrix"]]
        part_id = item["part_id"]
        line = (
            f"1 {color} {x:g} {y:g} {z:g} "
            f"{matrix[0]:g} {matrix[1]:g} {matrix[2]:g} "
            f"{matrix[3]:g} {matrix[4]:g} {matrix[5]:g} "
            f"{matrix[6]:g} {matrix[7]:g} {matrix[8]:g} {part_id}"
        )
        lines.append(line)
    return lines
