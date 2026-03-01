from __future__ import annotations

from pathlib import Path
import shutil

from sqlalchemy import select
from sqlalchemy.orm import Session

from engine.persistence.models import Branch, Candidate, Run, Step


class RunManager:
    def __init__(self, db: Session, run_dir: Path):
        self.db = db
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def create_run(self, name: str, workspace_id: str, concept_image: str, knobs_json: dict) -> Run:
        run = Run(name=name, workspace_id=workspace_id, concept_image=concept_image, knobs_json=knobs_json, status="running")
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_run(self, run_id: str) -> Run:
        run = self.db.get(Run, run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")
        return run

    def latest_run_by_name(self, name: str) -> Run | None:
        stmt = select(Run).where(Run.name == name).order_by(Run.created_at.desc())
        return self.db.scalars(stmt).first()

    def stop_run(self, run_id: str) -> Run:
        run = self.get_run(run_id)
        run.status = "stopped"
        self.db.commit()
        self.db.refresh(run)
        return run

    def complete_run(self, run_id: str) -> Run:
        run = self.get_run(run_id)
        run.status = "completed"
        self.db.commit()
        self.db.refresh(run)
        return run

    def fail_run(self, run_id: str) -> Run:
        run = self.get_run(run_id)
        run.status = "failed"
        self.db.commit()
        self.db.refresh(run)
        return run

    def should_stop(self, run_id: str) -> bool:
        return self.get_run(run_id).status == "stopped"

    def write_report(self, run_id: str, control_plane_base: str) -> Path:
        run = self.get_run(run_id)
        stmt = select(Step).where(Step.run_id == run_id).order_by(Step.step_index.asc())
        steps = list(self.db.scalars(stmt).all())

        lines = [
            f"# AI Build Run Report: {run.name}",
            "",
            f"- Run ID: {run.id}",
            f"- Workspace ID: {run.workspace_id}",
            f"- Status: {run.status}",
            f"- Concept: {run.concept_image}",
            "",
            "## Steps",
        ]

        for step in steps:
            lines.append(f"### Step {step.step_index}")
            lines.append(f"- Goal: `{step.goal_json}`")
            for branch in step.branches:
                lines.append(f"- Branch {branch.id}: score={branch.score_total:.4f}, status={branch.status}")
                for candidate in branch.candidates:
                    lines.append(
                        f"  - Candidate {candidate.id}: accepted={candidate.accepted}, scores={candidate.scores_json}"
                    )
            lines.append(
                f"- Timeline: {control_plane_base.rstrip('/')}/api/workspaces/{run.workspace_id}/timeline"
            )
            lines.append("")

        report_path = self.run_dir / f"report_{run_id}.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path

    def export_run(self, run_id: str, output_path: Path) -> Path:
        report_path = self.run_dir / f"report_{run_id}.md"
        if not report_path.exists():
            raise ValueError("Run report not found. Run `engine report` first.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report_path, output_path)
        return output_path

    def create_step(self, run_id: str, step_index: int, goal_json: dict) -> Step:
        step = Step(run_id=run_id, step_index=step_index, goal_json=goal_json)
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def create_branch(self, step_id: str, status: str = "pending") -> Branch:
        branch = Branch(step_id=step_id, status=status)
        self.db.add(branch)
        self.db.commit()
        self.db.refresh(branch)
        return branch

    def add_candidate(self, branch_id: str, assembly_json: dict, scores_json: dict, accepted: bool) -> Candidate:
        candidate = Candidate(
            branch_id=branch_id,
            assembly_json=assembly_json,
            scores_json=scores_json,
            accepted=accepted,
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate
