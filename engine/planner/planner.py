from __future__ import annotations

from pathlib import Path

from engine.providers.base import LLMProvider
from engine.prompts import load_system_prompt


class Planner:
    def __init__(self, provider: LLMProvider, plan_schema: dict):
        self.provider = provider
        self.plan_schema = plan_schema

    async def generate_plan(
        self,
        concept_image: Path,
        strategy_bucket_names: list[str],
        latest_timeline_summary: str,
        step_index: int,
    ) -> dict:
        system_prompt = load_system_prompt(
            "planner_system.txt",
            "You are a LEGO build planner. You produce one-step strategic intents for iterative micro-assembly construction.",
        )
        user_prompt = (
            f"Step {step_index}. Concept image path: {concept_image}.\n"
            f"Strategy buckets: {strategy_bucket_names}.\n"
            f"Latest timeline summary: {latest_timeline_summary}.\n"
            "Return planner JSON with focus, guidance, and stop signal."
        )
        return await self.provider.generate_json(system_prompt=system_prompt, user_prompt=user_prompt, schema=self.plan_schema)
