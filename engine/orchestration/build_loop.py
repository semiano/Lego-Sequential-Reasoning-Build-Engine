from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from engine.builder.generator import MicroAssemblyGenerator
from engine.config import EnginePreset
from engine.control_plane.client import ControlPlaneClient
from engine.evaluator.scorer import LocalScorer
from engine.orchestration.run_manager import RunManager
from engine.persistence.models import StrategyBucket
from engine.planner.planner import Planner


def _extract_render_rel_path(render_response: dict[str, Any]) -> str | None:
    for artifact in render_response.get("artifacts", []):
        if artifact.get("artifact_type") == "render" and str(artifact.get("rel_path", "")).endswith("iso.png"):
            return artifact.get("rel_path")
    return None


def _artifact_http_url(control_plane_base: str, workspace_id: str, rel_path: str) -> str:
    encoded = "/".join([quote(part) for part in rel_path.split("/")])
    return f"{control_plane_base.rstrip('/')}/api/workspaces/{workspace_id}/artifacts/{encoded}"


async def run_build_loop(
    db: Session,
    run_manager: RunManager,
    run_id: str,
    concept_image: Path,
    preset: EnginePreset,
    planner: Planner,
    builder: MicroAssemblyGenerator,
    scorer: LocalScorer,
    control_plane: ControlPlaneClient,
    control_plane_base: str,
    strategy_buckets: list[StrategyBucket],
    trace_dir: Path,
    start_step: int = 1,
) -> None:
    run = run_manager.get_run(run_id)
    best_score = -1.0
    plateau_count = 0

    for step_index in range(start_step, preset.max_steps + 1):
        if run_manager.should_stop(run_id):
            break

        timeline = await control_plane.get_timeline(run.workspace_id)
        timeline_summary = json.dumps({
            "step_count": len(timeline.get("steps", [])),
            "latest_kind": (timeline.get("steps", [{}])[-1].get("kind") if timeline.get("steps") else None),
        })

        plan = await planner.generate_plan(
            concept_image=concept_image,
            strategy_bucket_names=[bucket.name for bucket in strategy_buckets],
            latest_timeline_summary=timeline_summary,
            step_index=step_index,
        )

        plan_trace = trace_dir / f"step_{step_index:04d}_plan.json"
        plan_trace.write_text(json.dumps(plan, indent=2), encoding="utf-8")

        step_record = run_manager.create_step(run_id=run_id, step_index=step_index, goal_json=plan)
        if plan.get("stop_signal"):
            run_manager.complete_run(run_id)
            return

        branch_limit = max(1, preset.beam_width)
        branch_scores: list[tuple[float, dict, list[str], dict, int]] = []

        for branch_idx in range(branch_limit):
            for candidate_idx in range(preset.candidates_per_step):
                assembly_json, ldraw_lines = await builder.generate_candidate(
                    plan=plan,
                    branch_index=branch_idx,
                    candidate_index=candidate_idx,
                )
                if len(ldraw_lines) < 3:
                    continue
                heuristic_score = min(1.0, len(ldraw_lines) / float(max(3, plan.get("target_part_count", 6))))
                branch_scores.append((heuristic_score, assembly_json, ldraw_lines, {"heuristic": heuristic_score}, branch_idx))

        if not branch_scores:
            run_manager.fail_run(run_id)
            return

        branch_scores.sort(key=lambda x: x[0], reverse=True)
        top_branches = branch_scores[:branch_limit]
        winner = top_branches[0]
        _, winner_assembly, winner_lines, winner_scores, winner_branch_idx = winner

        branch_records = []
        for idx, branch_tuple in enumerate(top_branches):
            heuristic, assembly_json, _lines, heuristic_scores, branch_idx = branch_tuple
            branch_record = run_manager.create_branch(
                step_record.id,
                status="selected" if idx == 0 else "rejected",
            )
            branch_record.score_total = heuristic
            db.commit()
            run_manager.add_candidate(
                branch_id=branch_record.id,
                assembly_json=assembly_json,
                scores_json={**heuristic_scores, "heuristic_rank": idx + 1, "branch_index": branch_idx},
                accepted=idx == 0,
            )
            branch_records.append(branch_record)

        run_tag = f"[RUN:{run_id}] STEP:{step_index} BRANCH:{winner_branch_idx}"
        await control_plane.append_lines(
            run.workspace_id,
            winner_lines,
            message=f"{run_tag} intent={plan.get('intent', 'n/a')}",
        )
        render_response = await control_plane.render(
            run.workspace_id,
            views=preset.render_views,
            turntable_frames=preset.turntable_frames,
            resolution={"w": preset.resolution.w, "h": preset.resolution.h},
            message=f"{run_tag} render",
        )

        render_rel_path = _extract_render_rel_path(render_response)
        if render_rel_path is None:
            run_manager.fail_run(run_id)
            return

        render_url = _artifact_http_url(control_plane_base, run.workspace_id, render_rel_path)
        tmp_render = trace_dir / f"step_{step_index:04d}_render.png"
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(render_url)
            response.raise_for_status()
            tmp_render.write_bytes(response.content)

        detailed_scores = scorer.score(
            concept_image=concept_image,
            render_image=tmp_render,
            part_count=len(winner_lines),
            step_index=step_index,
        )

        winner_branch_record = branch_records[0]
        winner_branch_record.status = "completed"
        winner_branch_record.score_total = detailed_scores["score_total"]
        db.commit()

        for loser in branch_records[1:]:
            loser.status = "rejected"
        db.commit()

        await control_plane.checkpoint(
            run.workspace_id,
            message=f"{run_tag} winner checkpoint score={detailed_scores['score_total']:.4f}",
        )

        if detailed_scores["score_total"] > best_score + 1e-4:
            best_score = detailed_scores["score_total"]
            plateau_count = 0
        else:
            plateau_count += 1

        if best_score >= preset.score_threshold:
            run_manager.complete_run(run_id)
            return

        if plateau_count >= preset.plateau_patience:
            run_manager.complete_run(run_id)
            return

    run_manager.complete_run(run_id)
