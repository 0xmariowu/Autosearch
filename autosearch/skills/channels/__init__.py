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
    channels_root = _CHANNELS_ROOT.resolve()
    channel_part = Path(channel_name)
    module_part = Path(module_relative_path)
    if channel_part.is_absolute() or module_part.is_absolute():
        raise ValueError("channel module paths must be relative")

    channel_root = (channels_root / channel_part).resolve()
    module_path = (channel_root / module_part).resolve()
    if not channel_root.is_relative_to(channels_root):
        raise ValueError(f"Channel path {channel_root} escapes channels root")
    if not module_path.is_relative_to(channel_root):
        raise ValueError(f"Module path {module_path} escapes channel root")

    spec = importlib.util.spec_from_file_location(
        module_name or f"{channel_name}_{module_path.stem}",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
