"""Planner stage for research-oriented search execution."""

from __future__ import annotations

from typing import Any


def build_research_plan(
    *,
    searcher: Any,
    bundle_state: dict[str, Any],
    judge_result: dict[str, Any],
    tried_queries: set[str],
    available_providers: list[str],
    active_program: dict[str, Any],
    round_history: list[dict[str, Any]],
    plan_count: int,
    max_queries: int,
) -> list[dict[str, Any]]:
    plans = searcher.candidate_plans(
        bundle_state=bundle_state,
        judge_result=judge_result,
        tried_queries=tried_queries,
        available_providers=available_providers,
        active_program=active_program,
        round_history=round_history,
        plan_count=plan_count,
        max_queries=max_queries,
    )
    normalized: list[dict[str, Any]] = []
    for plan in list(plans or []):
        queries = list(plan.get("queries") or [])
        normalized.append({
            "label": str(plan.get("label") or "plan"),
            "queries": queries,
            "intents": queries,
            "program_overrides": dict(plan.get("program_overrides") or {}),
        })
    return normalized
