# Self-written, plan autosearch-0418-channels-and-skills.md § F003
from __future__ import annotations

import os
from pathlib import Path

import structlog

from autosearch.channels.base import Channel, ChannelRegistry, Environment
from autosearch.channels.demo import DemoChannel
from autosearch.core.environment_probe import probe_environment
from autosearch.observability.channel_health import ChannelHealth

LOGGER = structlog.get_logger(__name__).bind(component="channel_bootstrap")


def _default_channels_root() -> Path:
    return Path(__file__).resolve().parent.parent / "skills" / "channels"


def _build_channels(
    *,
    channels_root: Path | None = None,
    env: Environment | None = None,
) -> list[Channel]:
    if os.getenv("AUTOSEARCH_LLM_MODE") == "dummy":
        return [DemoChannel()]

    root = channels_root or _default_channels_root()
    if not root.is_dir():
        LOGGER.warning("channel_skills_root_missing", channels_root=str(root))
        return [DemoChannel()]

    registry = ChannelRegistry.compile_from_skills(root, env or probe_environment())
    # Wire a runtime ChannelHealth so cooldown/circuit-breaker actually fires;
    # without this the `_health_provider` always returned None and every
    # `_record_health` call inside `_CompiledChannel.search` was a no-op.
    registry.attach_health(ChannelHealth())
    channels = registry.available()
    if not channels:
        return [DemoChannel()]
    return channels
