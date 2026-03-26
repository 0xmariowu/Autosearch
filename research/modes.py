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
    branch_budget_per_round: dict[str, int]
    plateau_rounds: int
    stop_on_saturated: bool
    max_findings_before_search_disable: int
    disabled_actions: tuple[str, ...]

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
        branch_budget_per_round={
            "breadth": 1,
            "repair": 1,
            "followup": 0,
            "probe": 0,
            "research": 0,
        },
        plateau_rounds=1,
        stop_on_saturated=True,
        max_findings_before_search_disable=18,
        disabled_actions=("cross_verify",),
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
        branch_budget_per_round={
            "breadth": 1,
            "repair": 2,
            "followup": 1,
            "probe": 1,
            "research": 1,
        },
        plateau_rounds=3,
        stop_on_saturated=False,
        max_findings_before_search_disable=40,
        disabled_actions=(),
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
        branch_budget_per_round={
            "breadth": 1,
            "repair": 3,
            "followup": 2,
            "probe": 2,
            "research": 2,
        },
        plateau_rounds=4,
        stop_on_saturated=False,
        max_findings_before_search_disable=80,
        disabled_actions=(),
    ),
}


def normalize_mode(mode: str | None) -> ResearchModeName:
    value = str(mode or "balanced").strip().lower()
    if value in MODE_POLICIES:
        return value  # type: ignore[return-value]
    return "balanced"


def get_mode_policy(
    mode: str | None, overrides: dict[str, Any] | None = None
) -> ResearchModePolicy:
    normalized = normalize_mode(mode)
    base = MODE_POLICIES[normalized].to_dict()
    for key, value in dict(overrides or {}).items():
        if key in base and value is not None:
            base[key] = value
    return ResearchModePolicy(**base)  # type: ignore[arg-type]
