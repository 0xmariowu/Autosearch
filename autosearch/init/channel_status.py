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


def compile_channel_statuses(
    channels_root: Path, env: Environment | None = None
) -> list[ChannelStatus]:
    """Bug 2 (fix-plan): one source of truth for channel status.

    Previously this scanned the registry independently from `doctor.scan_channels`,
    which produced diverging counts (e.g. doctor 37/40 vs init 38/40). Now it
    delegates to doctor and only translates the row shape into init's
    presentation-layer enum (tier label, available/blocked/scaffold-only).

    The `env` argument is kept for backward compatibility but no longer used —
    doctor reads the live process environment itself.
    """
    # Lazy-import to avoid a top-level cycle and to keep doctor as the canonical
    # availability owner.
    from autosearch.core.doctor import scan_channels as _doctor_scan

    return [_doctor_status_to_init_status(row) for row in _doctor_scan(channels_root)]


_DOCTOR_TIER_TO_INIT_TIER: dict[int, Tier] = {0: "t0", 1: "t1", 2: "t2"}


def _doctor_status_to_init_status(row: object) -> ChannelStatus:
    """Translate a doctor row into the init-CLI ChannelStatus presentation."""
    tier: Tier = _DOCTOR_TIER_TO_INIT_TIER.get(row.tier, "t0")
    unmet = list(row.unmet_requires)
    impl_missing = [u for u in unmet if u.startswith("impl_missing")]
    real_unmet = [u for u in unmet if not u.startswith("impl_missing")]

    if row.status == "ok":
        status: Status = "available"
        return ChannelStatus(channel=row.channel, tier=tier, status=status, unmet_requires=[])

    # status in ("warn", "off"). `warn` means "some methods work, some don't" —
    # match doctor's strict headline counting where only `ok` counts as
    # "available". Surface real blockers in unmet_requires so the user can fix.
    if impl_missing and not real_unmet:
        return ChannelStatus(
            channel=row.channel, tier="scaffold", status="scaffold-only", unmet_requires=[]
        )
    return ChannelStatus(
        channel=row.channel, tier=tier, status="blocked", unmet_requires=real_unmet
    )


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
