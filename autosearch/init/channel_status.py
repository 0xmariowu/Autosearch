from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from autosearch.channels.base import ChannelMetadata, ChannelRegistry, CompiledMethod, Environment

Tier = Literal["t0", "t1", "t2", "scaffold"]
Status = Literal["available", "blocked", "scaffold-only"]

TIER_ORDER: tuple[Tier, ...] = ("t0", "t1", "t2", "scaffold")
TIER_LABELS: dict[Tier, str] = {
    "t0": "Tier 0 - always-on",
    "t1": "Tier 1 - env/API gated",
    "t2": "Tier 2 - login/cookie gated",
    "scaffold": "Scaffold-only (channel templates not shipped)",
}

_TIER2_REQUIRES_PATTERNS = ("COOKIES", "COOKIE", "SESSION", "SESSDATA", "AUTH_TOKEN")


@dataclass(frozen=True, slots=True)
class ChannelStatus:
    channel: str
    tier: Tier
    status: Status
    unmet_requires: list[str]


def default_channels_root() -> Path:
    return Path(__file__).resolve().parent.parent / "skills" / "channels"


def infer_tier(metadata: ChannelMetadata) -> Tier:
    """Return the visibility tier for a channel based on shipped methods."""

    if metadata.tier is not None:
        return _DECLARED_TIER_MAP.get(metadata.tier, "t0")

    return infer_tier_from_requires(
        [method.skill_method.requires for method in shipped_methods(metadata)]
    )


def shipped_methods(metadata: ChannelMetadata) -> list[CompiledMethod]:
    return [method for method in metadata.methods if "impl_missing" not in method.unmet_requires]


def summarize_registry(registry: ChannelRegistry) -> list[ChannelStatus]:
    rows: list[ChannelStatus] = []
    for channel in sorted(registry.all_channels(), key=lambda item: item.name):
        metadata = registry.metadata(channel.name)
        tier = infer_tier(metadata)
        if tier == "scaffold":
            rows.append(
                ChannelStatus(
                    channel=metadata.name,
                    tier=tier,
                    status="scaffold-only",
                    unmet_requires=[],
                )
            )
            continue

        available = any(method.available for method in shipped_methods(metadata))
        rows.append(
            ChannelStatus(
                channel=metadata.name,
                tier=tier,
                status="available" if available else "blocked",
                unmet_requires=[] if available else blocked_requires(metadata),
            )
        )
    return rows


def compile_channel_statuses(channels_root: Path, env: Environment) -> list[ChannelStatus]:
    registry = ChannelRegistry.compile_from_skills(channels_root, env, log_missing_impls=False)
    return summarize_registry(registry)


def blocked_requires(metadata: ChannelMetadata) -> list[str]:
    requires = {
        token
        for method in shipped_methods(metadata)
        for token in method.unmet_requires
        if token != "impl_missing"
    }
    return sorted(requires)


def required_env_tokens(metadata: ChannelMetadata) -> list[str]:
    return required_env_tokens_from_requires(
        [method.skill_method.requires for method in shipped_methods(metadata)]
    )


def infer_tier_from_requires(requires_by_method: list[list[str]]) -> Tier:
    if not requires_by_method:
        return "scaffold"
    if any(not requires for requires in requires_by_method):
        return "t0"
    if any(_requires_login(tokens) for tokens in requires_by_method):
        return "t2"
    return "t1"


def required_env_tokens_from_requires(requires_by_method: list[list[str]]) -> list[str]:
    return sorted(
        {token for requires in requires_by_method for token in requires if token.startswith("env:")}
    )


_DECLARED_TIER_MAP: dict[int, Tier] = {0: "t0", 1: "t1", 2: "t2"}


def _requires_login(tokens: list[str]) -> bool:
    for token in tokens:
        kind, _, value = token.partition(":")
        upper_value = value.upper()
        if kind == "cookie":
            return True
        if kind == "env" and any(pattern in upper_value for pattern in _TIER2_REQUIRES_PATTERNS):
            return True
    return False
