from dataclasses import dataclass


def is_valid_ldraw_line(line: str) -> bool:
    tokens = line.strip().split()
    if not tokens:
        return False
    if tokens[0] != "1":
        return False
    if len(tokens) < 15:
        return False
    try:
        int(tokens[1])
        for token in tokens[2:14]:
            float(token)
    except ValueError:
        return False
    return tokens[-1].lower().endswith(".dat")


def parse_part_id(line: str) -> str | None:
    tokens = line.strip().split()
    if len(tokens) < 15:
        return None
    return tokens[-1]


@dataclass
class Placement:
    part_id: str
    x: float
    y: float
    z: float


def parse_placements_from_text(content: str) -> list[Placement]:
    placements: list[Placement] = []
    for raw in content.splitlines():
        if not is_valid_ldraw_line(raw):
            continue
        tokens = raw.split()
        placements.append(
            Placement(
                part_id=tokens[-1],
                x=float(tokens[2]),
                y=float(tokens[3]),
                z=float(tokens[4]),
            )
        )
    return placements
