"""Helpers for applying research modes to runtime programs."""

from __future__ import annotations

from typing import Any

from .modes import get_mode_policy


def apply_mode_policy(program: dict[str, Any]) -> dict[str, Any]:
    updated = dict(program or {})
    policy = get_mode_policy(
        str(updated.get("mode") or "balanced"),
        dict(updated.get("mode_policy_overrides") or {}),
    )
    updated["mode"] = policy.name
    updated["resolved_mode_policy"] = policy.to_dict()

    population_policy = dict(updated.get("population_policy") or {})
    population_policy["plan_count"] = max(int(population_policy.get("plan_count", 0) or 0), int(policy.max_plan_count))
    population_policy["max_queries"] = max(int(population_policy.get("max_queries", 0) or 0), int(policy.max_queries))
    population_policy["max_branch_depth"] = max(int(population_policy.get("max_branch_depth", 0) or 0), int(policy.max_branch_depth))
    branch_budget = dict(population_policy.get("branch_budget_per_round") or {})
    for key, value in dict(policy.branch_budget_per_round or {}).items():
        branch_budget[str(key)] = max(int(branch_budget.get(key, 0) or 0), int(value or 0))
    population_policy["branch_budget_per_round"] = branch_budget
    updated["population_policy"] = population_policy

    updated["plan_count"] = int(policy.max_plan_count)
    updated["max_queries"] = int(policy.max_queries)

    sampling_policy = dict(updated.get("sampling_policy") or {})
    sampling_policy.setdefault("rank_by_relevance", True)
    sampling_policy["rerank_profile"] = str(sampling_policy.get("rerank_profile") or policy.rerank_profile)
    if policy.name == "deep":
        sampling_policy["semantic_query_dedup"] = True
    updated["sampling_policy"] = sampling_policy

    acquisition_policy = dict(updated.get("acquisition_policy") or {})
    acquisition_policy["acquire_pages"] = bool(acquisition_policy.get("acquire_pages", False)) or bool(policy.enable_acquisition)
    acquisition_policy["page_fetch_limit"] = max(
        int(acquisition_policy.get("page_fetch_limit", 0) or 0),
        int(policy.page_fetch_limit),
    ) if acquisition_policy["acquire_pages"] else 0
    updated["acquisition_policy"] = acquisition_policy

    evidence_policy = dict(updated.get("evidence_policy") or {})
    evidence_policy["prefer_acquired_text"] = bool(evidence_policy.get("prefer_acquired_text", False)) or bool(policy.prefer_acquired_text)
    evidence_policy["cross_verification"] = bool(evidence_policy.get("cross_verification", False)) or bool(policy.enable_cross_verification)
    updated["evidence_policy"] = evidence_policy

    repair_policy = dict(updated.get("repair_policy") or {})
    repair_policy["enable_recursive_repair"] = bool(repair_policy.get("enable_recursive_repair", False)) or bool(policy.enable_recursive_repair)
    updated["repair_policy"] = repair_policy

    stop_rules = dict(updated.get("stop_rules") or {})
    stop_rules["plateau_rounds"] = max(int(stop_rules.get("plateau_rounds", 0) or 0), int(policy.plateau_rounds))
    stop_rules.setdefault("stop_on_saturated", bool(policy.stop_on_saturated))
    updated["stop_rules"] = stop_rules

    action_policy_defaults = dict(updated.get("action_policy_defaults") or {})
    action_policy_defaults.setdefault("disabled_actions", list(policy.disabled_actions))
    action_policy_defaults["max_findings_before_search_disable"] = max(
        int(action_policy_defaults.get("max_findings_before_search_disable", 0) or 0),
        int(policy.max_findings_before_search_disable),
    )
    updated["action_policy_defaults"] = action_policy_defaults

    return updated
