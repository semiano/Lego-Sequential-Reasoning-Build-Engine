import asyncio

from engine.geometry.model_summary import summarize_model_state


def test_bbox_and_center_anchor_without_append_timeline():
    model = "\n".join(
        [
            "0 Untitled model",
            "1 16 0 8 0 1 0 0 0 1 0 0 0 1 3001.dat",
            "1 16 40 24 -20 1 0 0 0 1 0 0 0 1 3002.dat",
        ]
    )

    async def _fetch_artifact_text(_rel_path: str) -> str:
        return ""

    summary = asyncio.run(
        summarize_model_state(
            current_model_text=model,
            timeline={"steps": []},
            fetch_artifact_text=_fetch_artifact_text,
            recent_limit=20,
        )
    )

    assert summary["bbox"] == {
        "min_x": 0.0,
        "max_x": 40.0,
        "min_y": 8.0,
        "max_y": 24.0,
        "min_z": -20.0,
        "max_z": 0.0,
    }
    assert summary["anchor"] == {"x": 20.0, "y": 16.0, "z": -10.0}
    assert summary["part_count"] == 2


def test_last_append_centroid_anchor_from_snapshot_diff():
    current_model = "\n".join(
        [
            "1 16 0 8 0 1 0 0 0 1 0 0 0 1 3001.dat",
            "1 16 20 8 0 1 0 0 0 1 0 0 0 1 3002.dat",
            "1 16 40 8 0 1 0 0 0 1 0 0 0 1 3003.dat",
        ]
    )

    prev_snapshot = "\n".join(
        [
            "1 16 0 8 0 1 0 0 0 1 0 0 0 1 3001.dat",
        ]
    )
    last_append_snapshot = current_model

    timeline = {
        "steps": [
            {
                "step_index": 1,
                "kind": "checkpoint",
                "artifacts": [{"artifact_type": "ldraw", "rel_path": "model/step_0001.ldr"}],
            },
            {
                "step_index": 2,
                "kind": "append",
                "artifacts": [{"artifact_type": "ldraw", "rel_path": "model/step_0002.ldr"}],
            },
        ]
    }

    snapshots = {
        "model/step_0001.ldr": prev_snapshot,
        "model/step_0002.ldr": last_append_snapshot,
    }

    async def _fetch_artifact_text(rel_path: str) -> str:
        return snapshots[rel_path]

    summary = asyncio.run(
        summarize_model_state(
            current_model_text=current_model,
            timeline=timeline,
            fetch_artifact_text=_fetch_artifact_text,
            recent_limit=20,
        )
    )

    assert summary["anchor"] == {"x": 30.0, "y": 8.0, "z": 0.0}
    assert len(summary["recent_additions"]) >= 2
