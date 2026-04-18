# Self-written, plan autosearch-0418-channels-and-skills.md § F003
from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import structlog

from autosearch.channels.base import Environment
from autosearch.skills import SkillLoadError, load_all

LOGGER = structlog.get_logger(__name__).bind(component="environment_probe")
KNOWN_ENV_KEYS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "YOUTUBE_API_KEY",
    "GITHUB_TOKEN",
    "TWITTER_BEARER_TOKEN",
}


def _default_channels_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "channels"


def _discover_env_keys_from_skills(channels_root: Path) -> set[str]:
    try:
        specs = load_all(channels_root)
    except SkillLoadError as exc:
        LOGGER.warning(
            "environment_probe_skill_scan_failed",
            channels_root=str(channels_root),
            reason=str(exc),
        )
        return set()

    keys: set[str] = set()
    for spec in specs:
        for method in spec.methods:
            for token in method.requires:
                kind, value = token.split(":", maxsplit=1)
                if kind == "env":
                    keys.add(value)
    return keys


def probe_environment(
    cookies_dir: Path | None = None,
    env_keys_to_check: Iterable[str] | None = None,
) -> Environment:
    """Build an Environment from the current shell + filesystem.

    env_keys_to_check: if provided, only those keys are probed; otherwise probes any
    env var that some skill's requires list mentions (compile-time discovery).
    Practical default: probe a known set (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY,
    YOUTUBE_API_KEY, GITHUB_TOKEN, TWITTER_BEARER_TOKEN).
    """

    keys_to_check = (
        set(env_keys_to_check)
        if env_keys_to_check is not None
        else _discover_env_keys_from_skills(_default_channels_root()) | KNOWN_ENV_KEYS
    )
    env_keys = {key for key in keys_to_check if os.environ.get(key)}

    root = (cookies_dir or Path("~/.autosearch/cookies")).expanduser()
    cookies = {path.stem for path in root.glob("*.json")} if root.is_dir() else set()

    return Environment(
        cookies=cookies,
        mcp_servers=set(),
        env_keys=env_keys,
        binaries=set(),
    )
