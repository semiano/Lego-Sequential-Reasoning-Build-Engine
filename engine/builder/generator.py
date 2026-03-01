from __future__ import annotations

from engine.providers.base import LLMProvider
from engine.builder.ldraw_converter import assembly_to_ldraw_lines
from engine.prompts import load_system_prompt


class MicroAssemblyGenerator:
    def __init__(self, provider: LLMProvider, schema: dict):
        self.provider = provider
        self.schema = schema

    async def generate_candidate(self, plan: dict, branch_index: int, candidate_index: int) -> tuple[dict, list[str]]:
        system_prompt = load_system_prompt(
            "builder_system.txt",
            "You generate LEGO micro-assemblies (3-20 parts) as strict JSON.",
        )
        user_prompt = (
            f"Plan intent: {plan.get('intent')}\n"
            f"Region focus: {plan.get('region_focus')}\n"
            f"Guidance: {plan.get('micro_assembly_guidance')}\n"
            f"Branch: {branch_index}, Candidate: {candidate_index}.\n"
            "Return varied but coherent assemblies."
        )
        assembly_json = await self.provider.generate_json(system_prompt=system_prompt, user_prompt=user_prompt, schema=self.schema)
        lines = assembly_to_ldraw_lines(assembly_json)
        return assembly_json, lines
