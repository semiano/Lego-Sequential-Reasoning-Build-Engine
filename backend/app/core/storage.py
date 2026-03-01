from pathlib import Path

from app.core.config import get_settings


def ensure_data_dirs() -> Path:
    settings = get_settings()
    root = settings.resolved_data_dir
    (root / "workspaces").mkdir(parents=True, exist_ok=True)
    return root


def workspace_root(workspace_id: str) -> Path:
    return ensure_data_dirs() / "workspaces" / workspace_id


def ensure_workspace_dirs(workspace_id: str) -> Path:
    root = workspace_root(workspace_id)
    (root / "model").mkdir(parents=True, exist_ok=True)
    (root / "renders").mkdir(parents=True, exist_ok=True)
    (root / "meta").mkdir(parents=True, exist_ok=True)
    current = root / "model" / "current.ldr"
    if not current.exists():
        current.write_text("0 Untitled model\n", encoding="utf-8")
    return root


def resolve_workspace_file_safe(workspace_id: str, rel_path: str) -> Path:
    root = workspace_root(workspace_id).resolve()
    target = (root / rel_path).resolve()
    if root not in target.parents and target != root:
        raise ValueError("Invalid artifact path")
    return target
