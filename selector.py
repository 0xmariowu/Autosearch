"""Selection rules for autoresearch-style goal loops."""

from __future__ import annotations

from typing import Any


def _dimension_profile(payload: dict[str, Any]) -> tuple[int, ...]:
    scores = payload.get("dimension_scores") or {}
    return tuple(sorted(int(value or 0) for value in scores.values()))


def evaluate_acceptance(
    *,
    current_state: dict[str, Any],
    candidate_score: int,
    candidate_dimensions: dict[str, Any],
    candidate_metrics: dict[str, Any],
    harness: dict[str, Any],
    candidate_finding_count: int,
) -> dict[str, Any]:
    anti = dict(harness.get("anti_cheat") or {})
    hard_failures: list[str] = []
    warnings: list[str] = []

    if int(candidate_metrics.get("new_unique_urls", 0) or 0) < int(anti.get("min_new_unique_urls", 1) or 1):
        hard_failures.append("no_new_unique_urls")
    if float(candidate_metrics.get("novelty_ratio", 0.0) or 0.0) < float(anti.get("min_novelty_ratio", 0.01) or 0.01):
        hard_failures.append("novelty_too_low")
    if float(candidate_metrics.get("source_diversity", 0.0) or 0.0) < float(anti.get("min_source_diversity", 0.15) or 0.15):
        warnings.append("source_diversity_too_low")
    if float(candidate_metrics.get("source_concentration", 1.0) or 1.0) > float(anti.get("max_source_concentration", 0.82) or 0.82):
        warnings.append("source_concentration_too_high")
    if float(candidate_metrics.get("query_concentration", 1.0) or 1.0) > float(anti.get("max_query_concentration", 0.70) or 0.70):
        warnings.append("query_concentration_too_high")

    current_score = int(current_state.get("score", 0) or 0)
    current_profile = _dimension_profile(current_state)
    candidate_profile = _dimension_profile({"dimension_scores": candidate_dimensions})
    current_findings = int(len(current_state.get("accepted_findings", [])) or 0)
    new_unique_urls = int(candidate_metrics.get("new_unique_urls", 0) or 0)

    improved_score = candidate_score > current_score
    improved_profile = candidate_profile > current_profile
    improved_findings = candidate_finding_count > current_findings
    materially_new = new_unique_urls > 0

    accepted = False
    reason = "rejected"
    if improved_score and not hard_failures:
        accepted = True
        reason = "score_improved"
    elif candidate_score == current_score and not hard_failures and materially_new and (improved_profile or improved_findings):
        accepted = True
        reason = "tie_broken_by_profile_or_novelty"

    if accepted and warnings:
        reason = f"{reason}_with_warnings"

    return {
        "accepted": accepted,
        "reason": reason,
        "anti_cheat_failures": hard_failures,
        "anti_cheat_warnings": warnings,
        "current_score": current_score,
        "candidate_score": candidate_score,
        "current_profile": current_profile,
        "candidate_profile": candidate_profile,
    }


def candidate_rank(candidate: dict[str, Any]) -> tuple[int, int, int, int, int, int, int, int]:
    dimension_scores = candidate.get("dimension_scores") or {}
    balance = tuple(sorted(int(score or 0) for score in dimension_scores.values()))
    metrics = candidate.get("harness_metrics") or {}
    selection = candidate.get("selection") or {}
    return (
        int(candidate.get("score", 0) or 0),
        *balance,
        int(metrics.get("new_unique_urls", 0) or 0),
        -int(len(selection.get("anti_cheat_warnings", [])) or 0),
        int(candidate.get("matched_count", 0) or 0),
        int(candidate.get("finding_count", 0) or 0),
        -int(candidate.get("plan_index", 0) or 0),
    )
