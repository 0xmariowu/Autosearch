"""Packaged channel skill library shipped with autosearch."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_CHANNELS_ROOT = Path(__file__).resolve().parent
__all__ = ["resolve_skill_module"]


def resolve_skill_module(
    channel_name: str,
    module_relative_path: str,
    *,
    module_name: str | None = None,
) -> ModuleType:
    """Load a shipped channel module directly from the packaged skills tree."""
    module_path = _CHANNELS_ROOT / channel_name / module_relative_path
    spec = importlib.util.spec_from_file_location(
        module_name or f"{channel_name}_{module_path.stem}",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
