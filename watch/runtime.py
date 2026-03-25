"""Mode-aware goal watch execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from .models import GoalWatch


def run_watch(
    watch: GoalWatch | dict[str, Any],
    *,
    resolve_goal_case: Callable[[Any], dict[str, Any]],
    optimize_goal: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    model = watch if isinstance(watch, GoalWatch) else GoalWatch.from_mapping(dict(watch or {}))
    goal_case = dict(resolve_goal_case(model.goal_id))
    goal_case["mode"] = model.mode
    if model.provider_preferences:
        goal_case["providers"] = list(model.provider_preferences)
    budget = dict(model.budget or {})
    result = optimize_goal(
        goal_case,
        target_score=model.target_score,
        max_rounds=int(budget.get("rounds", 8) or 8),
        plateau_rounds=model.plateau_rounds,
        plan_count=int(budget.get("plan_count", 0) or 0) or None,
        max_queries=int(budget.get("max_queries", 0) or 0) or None,
        persist_run=True,
    )
    final_score = int(((result.get("bundle_final") or {}).get("score") or 0))
    return {
        "watch_id": model.watch_id,
        "goal_id": model.goal_id,
        "mode": model.mode,
        "frequency": model.frequency,
        "run_at": datetime.now().astimezone().isoformat(),
        "target_score": int(model.target_score or 100),
        "success_threshold": int(model.success_threshold or model.target_score),
        "goal_reached": final_score >= int(model.success_threshold or model.target_score),
        "score_gap": max(int(model.success_threshold or model.target_score) - final_score, 0),
        "stop_policy": dict(model.stop_rules or {}),
        "provider_preferences": list(model.provider_preferences or []),
        "budget": budget,
        "scheduler_summary": {
            "frequency": model.frequency,
            "plateau_rounds": int(model.plateau_rounds or 3),
            "should_run_again": not (final_score >= int(model.success_threshold or model.target_score)),
        },
        "final_score": final_score,
        "result": result,
    }


def run_watches(
    watches: list[GoalWatch | dict[str, Any]],
    *,
    resolve_goal_case: Callable[[Any], dict[str, Any]],
    optimize_goal: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    results = [
        run_watch(
            item,
            resolve_goal_case=resolve_goal_case,
            optimize_goal=optimize_goal,
        )
        for item in list(watches or [])
    ]
    return {
        "watch_count": len(results),
        "reached_count": sum(1 for item in results if bool(item.get("goal_reached"))),
        "results": results,
    }
