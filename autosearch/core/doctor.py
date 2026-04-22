"""Channel health scanner for autosearch doctor() MCP tool."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from autosearch.skills import SkillLoadError, load_all


@dataclass
class ChannelStatus:
    channel: str
    status: str  # "ok" | "warn" | "off"
    message: str
    unmet_requires: list[str]


def scan_channels(channels_root: Path | None = None) -> list[ChannelStatus]:
    """Scan all channel skills and return health status for each.

    status:
      ok   — all methods have their requires satisfied
      warn — at least one method available, some unmet
      off  — no methods available (all requires unmet or no methods)
    """
    root = channels_root or _default_channels_root()
    if not root.is_dir():
        return []

    try:
        specs = load_all(root)
    except SkillLoadError:
        return []

    env_keys = _current_env_keys()
    results: list[ChannelStatus] = []

    for spec in sorted(specs, key=lambda s: s.name):
        all_unmet: list[str] = []
        available_methods = 0
        for method in spec.methods:
            unmet = [token for token in method.requires if not _token_satisfied(token, env_keys)]
            if not unmet:
                available_methods += 1
            else:
                all_unmet.extend(unmet)

        if not spec.methods:
            status = "off"
            message = "no methods defined"
        elif available_methods == len(spec.methods):
            status = "ok"
            message = f"{available_methods}/{len(spec.methods)} methods available"
        elif available_methods > 0:
            status = "warn"
            unique_unmet = list(dict.fromkeys(all_unmet))
            message = (
                f"{available_methods}/{len(spec.methods)} methods available; "
                f"unmet: {', '.join(unique_unmet)}"
            )
        else:
            status = "off"
            unique_unmet = list(dict.fromkeys(all_unmet))
            message = f"no methods available; unmet: {', '.join(unique_unmet)}"

        results.append(
            ChannelStatus(
                channel=spec.name,
                status=status,
                message=message,
                unmet_requires=list(dict.fromkeys(all_unmet)),
            )
        )

    return results


def _token_satisfied(token: str, env_keys: set[str]) -> bool:
    kind, value = token.split(":", maxsplit=1)
    if kind == "env":
        return value in env_keys
    # cookie / mcp / binary: not checked here (env is the common case)
    return False


def _current_env_keys() -> set[str]:
    return {key for key, val in os.environ.items() if val}


def _default_channels_root() -> Path:
    return Path(__file__).resolve().parent.parent / "skills" / "channels"
