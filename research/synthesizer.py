"""Synthesizer stage for research-oriented search execution."""

from __future__ import annotations

from typing import Any

from evaluation_harness import build_bundle, bundle_metrics
from goal_judge import evaluate_goal_bundle
from .routeable_output import build_routeable_output


def synthesize_research_round(
    goal_case: dict[str, Any],
    *,
    existing_findings: list[dict[str, Any]],
    round_findings: list[dict[str, Any]],
    harness: dict[str, Any],
) -> dict[str, Any]:
    bundle = build_bundle(existing_findings, round_findings, harness)
    judge_result = evaluate_goal_bundle(goal_case, bundle)
    metrics = bundle_metrics(bundle, previous_bundle=existing_findings)
    weakest_dimension = ""
    dimension_scores = dict(judge_result.get("dimension_scores") or {})
    if dimension_scores:
        weakest_dimension = min(
            sorted(dimension_scores.keys()),
            key=lambda key: int(dimension_scores.get(key, 0) or 0),
        )
    return {
        "bundle": bundle,
        "judge_result": judge_result,
        "harness_metrics": metrics,
        "search_graph": {
            "bundle_size": len(bundle),
            "missing_dimensions": list(judge_result.get("missing_dimensions") or []),
            "weakest_dimension": weakest_dimension,
        },
        "repair_hints": {
            "weakest_dimension": weakest_dimension,
            "missing_dimensions": list(judge_result.get("missing_dimensions") or []),
            "follow_up_dimensions": list(judge_result.get("missing_dimensions") or [])[:2],
        },
        "routeable_output": build_routeable_output(
            goal_case,
            bundle=bundle,
            judge_result=judge_result,
            repair_hints={
                "weakest_dimension": weakest_dimension,
                "missing_dimensions": list(judge_result.get("missing_dimensions") or []),
                "follow_up_dimensions": list(judge_result.get("missing_dimensions") or [])[:2],
            },
        ),
    }
