from __future__ import annotations

from pathlib import Path


_PROMPT_DIR = Path(__file__).parent / "prompts"


def load_system_prompt(filename: str, fallback: str) -> str:
    path = _PROMPT_DIR / filename
    if not path.exists():
        return fallback
    content = path.read_text(encoding="utf-8").strip()
    return content or fallback
