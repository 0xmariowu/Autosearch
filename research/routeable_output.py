"""Build routeable outputs from synthesized research bundles."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .report_packet import build_research_packet


def _route_kind(record: dict[str, Any]) -> str:
    content_type = str(record.get("content_type") or "").strip()
    if content_type in {"code", "repository"}:
        return "implementation"
    if content_type in {"issue", "social"}:
        return "discussion"
    if content_type == "dataset":
        return "dataset"
    return "reference"


def build_routeable_output(
    goal_case: dict[str, Any],
    *,
    bundle: list[dict[str, Any]],
    judge_result: dict[str, Any],
    effective_target_score: int | None = None,
    repair_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repair_hints = dict(repair_hints or {})
    route_groups: dict[str, list[dict[str, Any]]] = {
        "implementation": [],
        "discussion": [],
        "dataset": [],
        "reference": [],
    }
    citations: list[str] = []
    for record in list(bundle or []):
        route_groups[_route_kind(record)].append({
            "title": str(record.get("title") or ""),
            "url": str(record.get("url") or ""),
            "source": str(record.get("source") or ""),
            "content_type": str(record.get("content_type") or ""),
        })
        url = str(record.get("url") or "").strip()
        if url and url not in citations:
            citations.append(url)
    keywords = Counter(
        term
        for record in list(bundle or [])
        for term in str(record.get("query") or "").lower().split()
        if len(term) >= 4
    )
    weakest_dimension = str(repair_hints.get("weakest_dimension") or "")
    cross_verification = dict(repair_hints.get("cross_verification") or {})
    handoff_packets = []
    for route_name, items in route_groups.items():
        if not items:
            continue
        handoff_packets.append({
            "route": route_name,
            "goal_id": str(goal_case.get("id") or ""),
            "target": route_name,
            "priority_dimension": weakest_dimension,
            "evidence_count": len(items),
            "top_items": items[:5],
            "next_action": "review_and_route" if route_name != "implementation" else "inspect_for_reuse",
        })
    next_actions = [
        {
            "type": "repair",
            "dimension": weakest_dimension,
            "mode": str(repair_hints.get("next_branch_mode") or "repair"),
        }
    ] if weakest_dimension else []
    research_packet = build_research_packet(
        goal_case=goal_case,
        bundle=bundle,
        judge_result=judge_result,
        cross_verification=cross_verification,
        next_actions=next_actions,
    ).to_dict()
    target_score = int(
        effective_target_score
        if effective_target_score is not None
        else goal_case.get("target_score", 100) or 100
    )
    return {
        "goal_id": str(goal_case.get("id") or ""),
        "goal_title": str(goal_case.get("title") or goal_case.get("problem") or ""),
        "score": int(judge_result.get("score", 0) or 0),
        "score_gap": max(target_score - int(judge_result.get("score", 0) or 0), 0),
        "matched_dimensions": list(judge_result.get("matched_dimensions") or []),
        "missing_dimensions": list(judge_result.get("missing_dimensions") or []),
        "weakest_dimension": weakest_dimension,
        "routes": route_groups,
        "next_actions": next_actions,
        "citations": citations[:20],
        "keywords": [term for term, _ in keywords.most_common(12)],
        "handoff_packets": handoff_packets,
        "research_packet": research_packet,
        "graph_handoff": {
            "merge_candidates": list(repair_hints.get("merge_candidates") or []),
            "prune_candidates": list(repair_hints.get("prune_candidates") or []),
            "next_branch_mode": str(repair_hints.get("next_branch_mode") or ""),
        },
        "planning_ops_summary": dict(repair_hints.get("planning_ops_summary") or {}),
        "gap_queue": list(repair_hints.get("gap_queue") or []),
        "cross_verification": {
            "enabled": bool(cross_verification.get("enabled")),
            "verification_queries": int(cross_verification.get("verification_queries", 0) or 0),
            "provider_count": int(cross_verification.get("provider_count", 0) or 0),
            "domain_count": int(cross_verification.get("domain_count", 0) or 0),
            "consensus_strength": str(cross_verification.get("consensus_strength") or ""),
            "contradiction_detected": bool(cross_verification.get("contradiction_detected", False)),
            "stance_counts": dict(cross_verification.get("stance_counts") or {}),
            "contradiction_signals": list(cross_verification.get("contradiction_signals") or []),
            "contradiction_pairs": list(cross_verification.get("contradiction_pairs") or []),
            "claim_alignment": list(cross_verification.get("claim_alignment") or []),
            "contradiction_clusters": list(cross_verification.get("contradiction_clusters") or []),
            "source_dispute_map": dict(cross_verification.get("source_dispute_map") or {}),
        },
    }
