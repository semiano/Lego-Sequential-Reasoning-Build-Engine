from __future__ import annotations

from engine.providers.base import LLMProvider
from engine.builder.ldraw_converter import assembly_to_ldraw_lines
from engine.prompts import load_system_prompt


class MicroAssemblyGenerator:
    def __init__(self, provider: LLMProvider, schema: dict):
        self.provider = provider
        self.schema = schema

    async def generate_candidate(
        self,
        plan: dict,
        branch_index: int,
        candidate_index: int,
        current_model_text: str,
        bbox: dict,
        anchor: dict,
        grid_rules: dict,
        part_palette: list[str],
        recent_lines: list[str],
        max_ldraw_lines_for_llm: int,
        violations: list[str] | None = None,
    ) -> tuple[dict, list[str]]:
        system_prompt = load_system_prompt(
            "builder_system.txt",
            "You generate LEGO micro-assemblies (3-20 parts) as strict JSON.",
        )
        model_lines = [line for line in current_model_text.splitlines() if line.strip()]
        include_full_model = len(model_lines) <= max_ldraw_lines_for_llm
        full_model_block = "\n".join(model_lines) if include_full_model else "<omitted: model too large>"

        violations_text = ""
        if violations:
            violations_text = "\nValidation violations to fix:\n- " + "\n- ".join(violations)

        user_prompt = (
            f"Plan intent: {plan.get('intent')}\n"
            f"Region focus: {plan.get('region_focus')}\n"
            f"Guidance: {plan.get('micro_assembly_guidance')}\n"
            f"Branch: {branch_index}, Candidate: {candidate_index}.\n"
            f"BBox: {bbox}\n"
            f"Anchor: {anchor}\n"
            f"Grid rules (LDraw LDU): {grid_rules}\n"
            f"Restricted part palette (max {len(part_palette)}): {part_palette}\n"
            "Recent model additions:\n"
            + "\n".join(recent_lines[:20])
            + "\n"
            + f"Include full current model in reasoning: {include_full_model}\n"
            + "Current model text:\n"
            + full_model_block
            + violations_text
            + "\nReturn varied but coherent assemblies."
        )
        assembly_json = await self.provider.generate_json(system_prompt=system_prompt, user_prompt=user_prompt, schema=self.schema)
        lines = assembly_to_ldraw_lines(assembly_json)
        return assembly_json, lines
