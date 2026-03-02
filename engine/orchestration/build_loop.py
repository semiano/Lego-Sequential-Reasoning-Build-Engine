from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from engine.builder.generator import MicroAssemblyGenerator
from engine.builder.ldraw_converter import assembly_to_ldraw_lines, existing_type1_hashset
from engine.config import EnginePreset
from engine.control_plane.client import ControlPlaneClient
from engine.evaluator.scorer import LocalScorer
from engine.geometry.model_summary import summarize_model_state
from engine.orchestration.run_manager import RunManager
from engine.persistence.models import StrategyBucket
from engine.planner.planner import Planner
from engine.validation.assembly_validator import validate_and_normalize


def _extract_render_rel_path(render_response: dict[str, Any]) -> str | None:
    for artifact in render_response.get("artifacts", []):
        if artifact.get("artifact_type") == "render" and str(artifact.get("rel_path", "")).endswith("iso.png"):
            return artifact.get("rel_path")
    return None


def _extract_temp_render_rel_path(render_response: dict[str, Any]) -> str | None:
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
        current_model_text = await control_plane.get_current_model_text(run.workspace_id)
        model_summary = await summarize_model_state(
            current_model_text=current_model_text,
            timeline=timeline,
            fetch_artifact_text=lambda rel_path: control_plane.get_artifact_text(run.workspace_id, rel_path),
            recent_limit=preset.recent_lines_limit,
        )

        derived_palette = []
        for line in model_summary.get("recent_lines", []):
            parts = line.strip().split()
            if len(parts) >= 15 and parts[0] == "1":
                part_id = parts[14]
                if part_id not in derived_palette:
                    derived_palette.append(part_id)

        palette = list(dict.fromkeys([*preset.part_palette, *derived_palette]))[: preset.part_palette_max_size]
        grid_rules = preset.grid_rules.model_dump()
        existing_hashset = existing_type1_hashset(current_model_text)

        timeline_summary = json.dumps({
            "step_count": len(timeline.get("steps", [])),
            "latest_kind": (timeline.get("steps", [{}])[-1].get("kind") if timeline.get("steps") else None),
            "part_count": model_summary.get("part_count", 0),
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
        candidate_results: list[tuple[float, dict, list[str], dict, int, int]] = []

        for branch_idx in range(branch_limit):
            for candidate_idx in range(preset.candidates_per_step):
                repair_violations: list[str] | None = None
                selected_candidate: tuple[dict, list[str], dict] | None = None
                for _attempt in range(2):
                    assembly_json, _ldraw_lines = await builder.generate_candidate(
                        plan=plan,
                        branch_index=branch_idx,
                        candidate_index=candidate_idx,
                        current_model_text=current_model_text,
                        bbox=model_summary["bbox"],
                        anchor=model_summary["anchor"],
                        grid_rules=grid_rules,
                        part_palette=palette,
                        recent_lines=model_summary.get("recent_lines", [])[:20],
                        max_ldraw_lines_for_llm=preset.max_ldraw_lines_for_llm,
                        violations=repair_violations,
                    )

                    ok, normalized_json, errors = validate_and_normalize(
                        assembly_json=assembly_json,
                        bbox=model_summary["bbox"],
                        anchor=model_summary["anchor"],
                        rules=grid_rules,
                        existing_lines_hashset=existing_hashset,
                    )
                    if ok:
                        normalized_lines = assembly_to_ldraw_lines(normalized_json)
                        selected_candidate = (normalized_json, normalized_lines, {"validation_errors": []})
                        break
                    repair_violations = errors

                if selected_candidate is None:
                    continue

                normalized_json, normalized_lines, validation_info = selected_candidate
                if len(normalized_lines) < 1:
                    continue

                temp_render = await control_plane.render_temp(
                    run.workspace_id,
                    extra_lines=normalized_lines,
                    views=preset.render_views,
                    turntable_frames=0,
                    resolution={"w": preset.resolution.w, "h": preset.resolution.h},
                )
                temp_rel_path = _extract_temp_render_rel_path(temp_render)
                if temp_rel_path is None:
                    continue

                temp_url = _artifact_http_url(control_plane_base, run.workspace_id, temp_rel_path)
                tmp_render = trace_dir / f"step_{step_index:04d}_branch_{branch_idx}_cand_{candidate_idx}.png"
                import httpx

                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.get(temp_url)
                    response.raise_for_status()
                    tmp_render.write_bytes(response.content)

                detailed_scores = scorer.score(
                    concept_image=concept_image,
                    render_image=tmp_render,
                    part_count=len(normalized_lines),
                    step_index=step_index,
                )
                score_total = float(detailed_scores["score_total"])
                candidate_results.append(
                    (
                        score_total,
                        normalized_json,
                        normalized_lines,
                        {
                            **detailed_scores,
                            **validation_info,
                            "temp_render_rel_path": temp_rel_path,
                        },
                        branch_idx,
                        candidate_idx,
                    )
                )

        if not candidate_results:
            run_manager.fail_run(run_id)
            return

        candidate_results.sort(key=lambda x: x[0], reverse=True)
        top_branches = candidate_results[:branch_limit]
        winner = top_branches[0]
        winner_score, winner_assembly, winner_lines, winner_scores, winner_branch_idx, winner_candidate_idx = winner

        branch_records = []
        for idx, branch_tuple in enumerate(top_branches):
            score_total, assembly_json, _lines, score_details, branch_idx, candidate_idx = branch_tuple
            branch_record = run_manager.create_branch(
                step_record.id,
                status="selected" if idx == 0 else "rejected",
            )
            branch_record.score_total = score_total
            db.commit()
            run_manager.add_candidate(
                branch_id=branch_record.id,
                assembly_json=assembly_json,
                scores_json={**score_details, "rank": idx + 1, "branch_index": branch_idx, "candidate_index": candidate_idx},
                accepted=idx == 0,
            )
            branch_records.append(branch_record)

        run_tag = f"[RUN:{run_id}] STEP:{step_index} BRANCH:{winner_branch_idx} CAND:{winner_candidate_idx}"
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

        winner_branch_record = branch_records[0]
        winner_branch_record.status = "completed"
        winner_branch_record.score_total = winner_score
        db.commit()

        for loser in branch_records[1:]:
            loser.status = "rejected"
        db.commit()

        await control_plane.checkpoint(
            run.workspace_id,
            message=f"{run_tag} winner checkpoint score={winner_score:.4f}",
        )

        if winner_score > best_score + 1e-4:
            best_score = winner_score
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
