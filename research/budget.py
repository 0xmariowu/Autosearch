"""Budget helpers for deep research loops."""

from __future__ import annotations

import math
from typing import Any


DEFAULT_BUDGET = {
    "explore_budget_pct": 0.85,
    "answer_budget_pct": 0.15,
    "provider_timeout_seconds": 10,
    "parallel_provider_limit": 6,
}


def budget_policy(program: dict[str, Any]) -> dict[str, Any]:
    policy = {**DEFAULT_BUDGET, **dict(program.get("budget_policy") or {})}
    policy["provider_timeout_seconds"] = int(policy.get("provider_timeout_seconds", 10) or 10)
    policy["parallel_provider_limit"] = int(policy.get("parallel_provider_limit", 6) or 6)
    return policy


def budget_state(*, program: dict[str, Any], round_index: int, max_rounds: int) -> dict[str, Any]:
    policy = budget_policy(program)
    explore_round_limit = max(1, math.ceil(float(policy["explore_budget_pct"]) * int(max_rounds or 1)))
    return {
        "policy": policy,
        "round_index": int(round_index),
        "explore_round_limit": explore_round_limit,
        "budget_exhausted": int(round_index) >= explore_round_limit,
    }


def should_stop_on_budget(
    *,
    program: dict[str, Any],
    round_index: int,
    max_rounds: int,
    current_score: int,
    target_score: int,
) -> bool:
    state = budget_state(program=program, round_index=round_index, max_rounds=max_rounds)
    if not state["budget_exhausted"]:
        return False
    if int(current_score or 0) >= int(target_score or 0):
        return True
    return int(round_index or 0) > int(state["explore_round_limit"] or 0)
