from engine.validation.assembly_validator import validate_and_normalize


def _base_bbox():
    return {"min_x": 0.0, "max_x": 40.0, "min_y": 8.0, "max_y": 24.0, "min_z": -20.0, "max_z": 20.0}


def _base_anchor():
    return {"x": 20.0, "y": 8.0, "z": 0.0}


def _base_rules():
    return {
        "xz_unit": 20,
        "y_unit": 8,
        "snap_mode": "snap",
        "snap_epsilon": 0.01,
        "bbox_margin": 80.0,
        "anchor_radius": 120.0,
        "require_axis_aligned_matrix": True,
    }


def test_snapping_applies_to_positions():
    assembly = {
        "assemblies": [
            {
                "color": 16,
                "position": {"x": 19.8, "y": 7.9, "z": 40.2},
                "matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                "part_id": "3001.dat",
                "intent_note": "base",
            }
        ]
    }

    ok, normalized, errors = validate_and_normalize(
        assembly_json=assembly,
        bbox=_base_bbox(),
        anchor=_base_anchor(),
        rules=_base_rules(),
        existing_lines_hashset=set(),
    )

    assert ok
    assert not errors
    assert normalized["assemblies"][0]["position"] == {"x": 20, "y": 8, "z": 40}


def test_reject_far_away_and_disconnected_candidate():
    assembly = {
        "assemblies": [
            {
                "color": 16,
                "position": {"x": 1000, "y": 800, "z": -1000},
                "matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                "part_id": "3001.dat",
                "intent_note": "floating",
            }
        ]
    }

    ok, _normalized, errors = validate_and_normalize(
        assembly_json=assembly,
        bbox=_base_bbox(),
        anchor=_base_anchor(),
        rules=_base_rules(),
        existing_lines_hashset=set(),
    )

    assert not ok
    assert any("too far" in error for error in errors)
    assert any("No connected placement" in error for error in errors)


def test_duplicate_detection_rejects_existing_placement():
    assembly = {
        "assemblies": [
            {
                "color": 16,
                "position": {"x": 20, "y": 8, "z": 0},
                "matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                "part_id": "3001.dat",
                "intent_note": "duplicate",
            }
        ]
    }

    existing = {
        "3001.dat|20,8,0|1,0,0,0,1,0,0,0,1"
    }

    ok, _normalized, errors = validate_and_normalize(
        assembly_json=assembly,
        bbox=_base_bbox(),
        anchor=_base_anchor(),
        rules=_base_rules(),
        existing_lines_hashset=existing,
    )

    assert not ok
    assert any("duplicates an existing placement" in error for error in errors)
