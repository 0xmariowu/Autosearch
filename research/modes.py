"""Mode contracts for search and research execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


ResearchModeName = Literal["speed", "balanced", "deep"]


@dataclass(frozen=True)
class ResearchModePolicy:
    name: ResearchModeName
    enable_planning: bool
    enable_cross_verification: bool
    enable_acquisition: bool
    enable_recursive_repair: bool
    emit_research_packet: bool
    max_branch_depth: int
    max_plan_count: int
    max_queries: int
    page_fetch_limit: int
    prefer_acquired_text: bool
    rerank_profile: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


MODE_POLICIES: dict[ResearchModeName, ResearchModePolicy] = {
    "speed": ResearchModePolicy(
        name="speed",
        enable_planning=False,
        enable_cross_verification=False,
        enable_acquisition=False,
        enable_recursive_repair=False,
        emit_research_packet=False,
        max_branch_depth=1,
        max_plan_count=1,
        max_queries=3,
        page_fetch_limit=0,
        prefer_acquired_text=False,
        rerank_profile="lexical",
    ),
    "balanced": ResearchModePolicy(
        name="balanced",
        enable_planning=True,
        enable_cross_verification=True,
        enable_acquisition=True,
        enable_recursive_repair=True,
        emit_research_packet=True,
        max_branch_depth=3,
        max_plan_count=3,
        max_queries=5,
        page_fetch_limit=2,
        prefer_acquired_text=False,
        rerank_profile="hybrid",
    ),
    "deep": ResearchModePolicy(
        name="deep",
        enable_planning=True,
        enable_cross_verification=True,
        enable_acquisition=True,
        enable_recursive_repair=True,
        emit_research_packet=True,
        max_branch_depth=5,
        max_plan_count=5,
        max_queries=7,
        page_fetch_limit=4,
        prefer_acquired_text=True,
        rerank_profile="hybrid",
    ),
}


def normalize_mode(mode: str | None) -> ResearchModeName:
    value = str(mode or "balanced").strip().lower()
    if value in MODE_POLICIES:
        return value  # type: ignore[return-value]
    return "balanced"


def get_mode_policy(mode: str | None, overrides: dict[str, Any] | None = None) -> ResearchModePolicy:
    normalized = normalize_mode(mode)
    base = MODE_POLICIES[normalized].to_dict()
    for key, value in dict(overrides or {}).items():
        if key in base and value is not None:
            base[key] = value
    return ResearchModePolicy(**base)  # type: ignore[arg-type]
