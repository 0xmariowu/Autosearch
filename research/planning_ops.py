"""Bounded planning operations for the research runtime."""

from __future__ import annotations

from typing import Any


def _normalize_topic_frontier(frontier: list[Any] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in list(frontier or []):
        if isinstance(item, dict):
            topic_id = str(item.get("id") or item.get("topic_id") or item.get("label") or "").strip()
            topic = dict(item)
            if topic_id:
                topic["id"] = topic_id
            normalized.append(topic)
            continue
        topic_id = str(item or "").strip()
        if topic_id:
            normalized.append({"id": topic_id, "queries": []})
    return normalized


def apply_planning_ops(program: dict[str, Any], ops: list[dict[str, Any]] | None) -> dict[str, Any]:
    updated = dict(program or {})
    if not ops:
        return updated
    for op in list(ops or []):
        kind = str((op or {}).get("op") or "").strip()
        target = str((op or {}).get("target") or "").strip()
        if kind == "request_cross_check":
            evidence_policy = dict(updated.get("evidence_policy") or {})
            evidence_policy["cross_verification_required"] = True
            cross = dict(updated.get("cross_verification_policy") or {})
            topics = list(cross.get("topics") or [])
            if target and target not in topics:
                topics.append(target)
            cross["topics"] = topics
            cross["mode"] = str((op or {}).get("mode") or cross.get("mode") or "cross_check")
            updated["evidence_policy"] = evidence_policy
            updated["cross_verification_policy"] = cross
        elif kind == "raise_budget":
            population_policy = dict(updated.get("population_policy") or {})
            increment = int((op or {}).get("amount", 1) or 1)
            population_policy["plan_count"] = max(int(population_policy.get("plan_count", 1) or 1) + increment, 1)
            population_policy["max_queries"] = max(int(population_policy.get("max_queries", 1) or 1) + increment, 1)
            updated["population_policy"] = population_policy
            updated["plan_count"] = max(int(updated.get("plan_count", 1) or 1) + increment, 1)
            updated["max_queries"] = max(int(updated.get("max_queries", 1) or 1) + increment, 1)
        elif kind == "add_branch":
            frontier = _normalize_topic_frontier(updated.get("topic_frontier") or [])
            frontier_ids = {str((item or {}).get("id") or "").strip() for item in frontier}
            if target and target not in frontier_ids:
                frontier.append({"id": target, "queries": []})
            updated["topic_frontier"] = frontier
            round_roles = list(updated.get("round_roles") or [])
            role = str((op or {}).get("role") or "").strip()
            if role and role not in round_roles:
                round_roles.append(role)
            updated["round_roles"] = round_roles
        elif kind == "mark_saturated":
            plateau_state = dict(updated.get("plateau_state") or {})
            stagnation = dict(plateau_state.get("dimension_stagnation") or {})
            if target:
                stagnation[target] = "saturated"
            plateau_state["dimension_stagnation"] = stagnation
            updated["plateau_state"] = plateau_state
        elif kind == "retire_branch":
            stats = dict(updated.get("evolution_stats") or {})
            retired = list(stats.get("retired_mutation_kinds") or [])
            branch_kind = str((op or {}).get("mutation_kind") or target or "").strip()
            if branch_kind and branch_kind not in retired:
                retired.append(branch_kind)
            stats["retired_mutation_kinds"] = retired
            updated["evolution_stats"] = stats
    return updated
