"""Selection rules for autoresearch-style goal loops."""

from __future__ import annotations

from typing import Any


def _dimension_profile(payload: dict[str, Any]) -> tuple[int, ...]:
    scores = payload.get("dimension_scores") or {}
    return tuple(sorted(int(value or 0) for value in scores.values()))


def _program_change_fields(current_program: dict[str, Any] | None, candidate_program: dict[str, Any] | None) -> list[str]:
    current_program = dict(current_program or {})
    candidate_program = dict(candidate_program or {})
    changed: list[str] = []
    for field in (
        "provider_mix",
        "search_backends",
        "backend_roles",
        "acquisition_policy",
        "evidence_policy",
        "repair_policy",
        "population_policy",
        "topic_frontier",
        "query_templates",
        "explore_budget",
        "exploit_budget",
        "sampling_policy",
    ):
        if current_program.get(field) != candidate_program.get(field):
            changed.append(field)
    return changed


def _provider_specialization_score(current_program: dict[str, Any] | None, candidate_program: dict[str, Any] | None) -> int:
    current_mix = list((current_program or {}).get("provider_mix") or [])
    candidate_mix = list((candidate_program or {}).get("provider_mix") or [])
    if not candidate_mix:
        return 0
    return max(0, len(current_mix) - len(candidate_mix))


def _dimension_improvements(
    current_dimensions: dict[str, Any] | None,
    candidate_dimensions: dict[str, Any] | None,
) -> tuple[list[str], int]:
    current_dimensions = dict(current_dimensions or {})
    candidate_dimensions = dict(candidate_dimensions or {})
    improved: list[str] = []
    weakest_delta = 0
    if current_dimensions:
        weakest_dim = min(
            current_dimensions.keys(),
            key=lambda key: int(current_dimensions.get(key, 0) or 0),
        )
        weakest_delta = int(candidate_dimensions.get(weakest_dim, 0) or 0) - int(current_dimensions.get(weakest_dim, 0) or 0)
    for dim_id in set(current_dimensions) | set(candidate_dimensions):
        if int(candidate_dimensions.get(dim_id, 0) or 0) > int(current_dimensions.get(dim_id, 0) or 0):
            improved.append(str(dim_id))
    return sorted(improved), int(weakest_delta)


def _repair_alignment_score(
    program_change_fields: list[str],
    *,
    improved_dimensions: list[str],
    weakest_dimension_delta: int,
) -> int:
    score = 0
    if weakest_dimension_delta > 0:
        score += 2
    if improved_dimensions:
        score += 1
    for field in ("repair_policy", "evidence_policy", "acquisition_policy", "search_backends", "backend_roles"):
        if field in program_change_fields:
            score += 1
    if "population_policy" in program_change_fields:
        score += 1
    return score


def evaluate_acceptance(
    *,
    current_state: dict[str, Any],
    candidate_score: int,
    candidate_dimensions: dict[str, Any],
    candidate_metrics: dict[str, Any],
    harness: dict[str, Any],
    candidate_finding_count: int,
    current_program: dict[str, Any] | None = None,
    candidate_program: dict[str, Any] | None = None,
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
    program_change_fields = _program_change_fields(current_program, candidate_program)
    program_changed = bool(program_change_fields)
    provider_specialization = _provider_specialization_score(current_program, candidate_program)
    improved_dimensions, weakest_dimension_delta = _dimension_improvements(
        current_state.get("dimension_scores"),
        candidate_dimensions,
    )
    repair_alignment = _repair_alignment_score(
        program_change_fields,
        improved_dimensions=improved_dimensions,
        weakest_dimension_delta=weakest_dimension_delta,
    )

    improved_score = candidate_score > current_score
    improved_profile = candidate_profile > current_profile
    improved_findings = candidate_finding_count > current_findings
    materially_new = new_unique_urls > 0

    accepted = False
    reason = "rejected"
    if improved_score and not hard_failures:
        accepted = True
        reason = "score_improved"
    elif candidate_score == current_score and not hard_failures and materially_new and (
        improved_profile or improved_findings or program_changed or bool(improved_dimensions)
    ):
        accepted = True
        reason = "tie_broken_by_profile_novelty_or_program"

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
        "program_changed": program_changed,
        "program_change_fields": program_change_fields,
        "repair_alignment": repair_alignment,
        "provider_specialization": provider_specialization,
        "improved_dimensions": improved_dimensions,
        "weakest_dimension_delta": weakest_dimension_delta,
    }


def candidate_rank(candidate: dict[str, Any]) -> tuple[int, int, int, int, int, int, int, int, int, int]:
    dimension_scores = candidate.get("dimension_scores") or {}
    balance = tuple(sorted(int(score or 0) for score in dimension_scores.values()))
    metrics = candidate.get("harness_metrics") or {}
    selection = candidate.get("selection") or {}
    return (
        int(candidate.get("score", 0) or 0),
        int(selection.get("weakest_dimension_delta", 0) or 0),
        int(selection.get("repair_alignment", 0) or 0),
        int(len(selection.get("improved_dimensions", [])) or 0),
        *balance,
        int(metrics.get("new_unique_urls", 0) or 0),
        int(selection.get("provider_specialization", 0) or 0),
        int(len(selection.get("program_change_fields", [])) or 0),
        -int(len(selection.get("anti_cheat_warnings", [])) or 0),
        int(candidate.get("matched_count", 0) or 0),
        int(candidate.get("finding_count", 0) or 0),
        -int(candidate.get("plan_index", 0) or 0),
    )
