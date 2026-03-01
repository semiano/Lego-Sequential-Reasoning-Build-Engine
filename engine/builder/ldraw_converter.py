from __future__ import annotations


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
