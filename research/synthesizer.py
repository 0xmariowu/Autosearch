"""Synthesizer stage for research-oriented search execution."""

from __future__ import annotations

from collections import Counter
from typing import Any

from evaluation_harness import build_bundle, bundle_metrics
from evidence.normalize import coerce_evidence_records
from goal_judge import evaluate_goal_bundle
from .bundle import ResearchBundle
from .routeable_output import build_routeable_output

POSITIVE_CLAIM_TERMS = {
    "works",
    "working",
    "passes",
    "passed",
    "verified",
    "reliable",
    "success",
    "successful",
    "stable",
}

NEGATIVE_CLAIM_TERMS = {
    "fails",
    "failed",
    "failing",
    "broken",
    "issue",
    "issues",
    "bug",
    "bugs",
    "limitation",
    "limitations",
    "criticism",
    "tradeoff",
    "tradeoffs",
    "regression",
}


def _query_cluster(bundle: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for item in list(bundle or []):
        query = str(item.get("query") or "").strip()
        if query:
            counts[query] += 1
    return [
        {"query": query, "count": count}
        for query, count in counts.most_common(8)
    ]


def _domain_cluster(bundle: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for item in list(bundle or []):
        domain = str(item.get("domain") or "").strip()
        if domain:
            counts[domain] += 1
    return [
        {"domain": domain, "count": count}
        for domain, count in counts.most_common(8)
    ]


def _graph_scheduler_hints(
    *,
    bundle: list[dict[str, Any]],
    judge_result: dict[str, Any],
    graph_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    graph_plan = dict(graph_plan or {})
    weakest_dimension = ""
    dimension_scores = dict(judge_result.get("dimension_scores") or {})
    if dimension_scores:
        weakest_dimension = min(
            sorted(dimension_scores.keys()),
            key=lambda key: int(dimension_scores.get(key, 0) or 0),
        )
    branch_targets = [str(item).strip() for item in list(graph_plan.get("branch_targets") or []) if str(item).strip()]
    query_clusters = _query_cluster(bundle)
    domain_clusters = _domain_cluster(bundle)
    merge_candidates = [
        item["query"]
        for item in query_clusters
        if int(item.get("count", 0) or 0) >= 2
    ][:4]
    prune_candidates = [
        item["domain"]
        for item in domain_clusters
        if int(item.get("count", 0) or 0) >= 4
    ][:4]
    next_branch_mode = "repair"
    if merge_candidates and weakest_dimension:
        next_branch_mode = "merge_and_repair"
    elif prune_candidates:
        next_branch_mode = "prune_and_probe"
    elif weakest_dimension:
        next_branch_mode = "deeper_repair"
    return {
        "branch_targets": branch_targets,
        "weakest_dimension": weakest_dimension,
        "query_clusters": query_clusters,
        "domain_clusters": domain_clusters,
        "merge_candidates": merge_candidates,
        "prune_candidates": prune_candidates,
        "next_branch_mode": next_branch_mode,
    }


def _cross_verification_summary(
    *,
    bundle: list[dict[str, Any]],
    graph_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    graph_plan = dict(graph_plan or {})
    decision = dict(graph_plan.get("decision") or {})
    query_runs = list(graph_plan.get("query_runs") or [])
    provider_count = len({
        str(item.get("source") or "").strip()
        for item in list(bundle or [])
        if str(item.get("source") or "").strip()
    })
    domain_count = len({
        str(item.get("domain") or "").strip()
        for item in list(bundle or [])
        if str(item.get("domain") or "").strip()
    })
    contradiction_terms = {"vs", "versus", "limitation", "limitations", "criticism", "tradeoff", "tradeoffs", "regression"}
    contradiction_signals = [
        str(item.get("title") or "")
        for item in list(bundle or [])
        if contradiction_terms.intersection(set(str(item.get("title") or "").lower().split()))
    ][:6]
    contradiction_pairs: list[dict[str, Any]] = []
    stance_counts = {"positive": 0, "negative": 0, "neutral": 0}
    for item in list(bundle or []):
        text = " ".join([
            str(item.get("title") or ""),
            str(item.get("extract") or ""),
            str(item.get("body") or ""),
        ]).lower()
        positive = any(term in text for term in POSITIVE_CLAIM_TERMS)
        negative = any(term in text for term in NEGATIVE_CLAIM_TERMS)
        if positive and not negative:
            stance = "positive"
        elif negative and not positive:
            stance = "negative"
        else:
            stance = "neutral"
        stance_counts[stance] += 1
        if stance != "neutral":
            contradiction_pairs.append(
                {
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("url") or ""),
                    "source": str(item.get("source") or ""),
                    "stance": stance,
                }
            )
    contradiction_detected = bool(stance_counts["positive"] and stance_counts["negative"])
    if contradiction_detected:
        consensus_strength = "contested"
    elif provider_count >= 3 and domain_count >= 2:
        consensus_strength = "high"
    elif provider_count >= 2:
        consensus_strength = "medium"
    else:
        consensus_strength = "low"
    return {
        "enabled": bool(decision.get("cross_verify")),
        "verification_queries": int(((graph_plan.get("cross_verification") or {}).get("verification_query_count", 0) or 0)),
        "provider_count": provider_count,
        "domain_count": domain_count,
        "consensus_strength": consensus_strength,
        "contradiction_detected": contradiction_detected,
        "stance_counts": stance_counts,
        "contradiction_signals": contradiction_signals,
        "contradiction_pairs": contradiction_pairs[:8],
        "query_run_count": len(query_runs),
    }


def _gap_queue_update(
    *,
    gap_queue: list[dict[str, Any]] | None,
    judge_result: dict[str, Any],
) -> list[dict[str, Any]]:
    missing = {str(item or "").strip() for item in list(judge_result.get("missing_dimensions") or []) if str(item or "").strip()}
    updated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in list(gap_queue or []):
        payload = dict(item)
        dimension = str(payload.get("dimension") or "").strip()
        if not dimension:
            continue
        payload["status"] = "open" if dimension in missing else "satisfied"
        updated.append(payload)
        seen.add(dimension)
    for dimension in missing:
        if dimension in seen:
            continue
        updated.append({
            "gap_id": f"gap:{dimension.replace(' ', '_')}",
            "dimension": dimension,
            "question": dimension.replace("_", " "),
            "priority": len(updated) + 1,
            "status": "open",
        })
    return updated


def synthesize_research_round(
    goal_case: dict[str, Any],
    *,
    existing_findings: list[dict[str, Any]],
    round_findings: list[dict[str, Any]],
    harness: dict[str, Any],
    graph_plan: dict[str, Any] | None = None,
    gap_queue: list[dict[str, Any]] | None = None,
    planning_ops: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    bundle = build_bundle(
        coerce_evidence_records(existing_findings),
        coerce_evidence_records(round_findings),
        harness,
    )
    judge_result = evaluate_goal_bundle(goal_case, bundle)
    research_bundle = ResearchBundle.from_parts(
        goal_id=str(goal_case.get("id") or "goal"),
        evidence_records=bundle,
        judge_result=judge_result,
        target_score=int(goal_case.get("target_score", 100) or 100),
    )
    metrics = bundle_metrics(bundle, previous_bundle=existing_findings)
    weakest_dimension = ""
    dimension_scores = dict(judge_result.get("dimension_scores") or {})
    if dimension_scores:
        weakest_dimension = min(
            sorted(dimension_scores.keys()),
            key=lambda key: int(dimension_scores.get(key, 0) or 0),
        )
    graph_scheduler = _graph_scheduler_hints(
        bundle=bundle,
        judge_result=judge_result,
        graph_plan=graph_plan,
    )
    cross_verification = _cross_verification_summary(
        bundle=bundle,
        graph_plan=graph_plan,
    )
    updated_gap_queue = _gap_queue_update(gap_queue=gap_queue, judge_result=judge_result)
    planning_ops_summary = {
        "count": len(list(planning_ops or [])),
        "ops": [
            {"op": str(item.get("op") or ""), "target": str(item.get("target") or "")}
            for item in list(planning_ops or [])[:6]
        ],
    }
    return {
        "bundle": bundle,
        "research_bundle": research_bundle.to_dict(),
        "judge_result": judge_result,
        "harness_metrics": metrics,
        "search_graph": {
            "goal_id": str(goal_case.get("id") or "goal"),
            "bundle_id": str(research_bundle.bundle_id),
            "bundle_size": len(bundle),
            "missing_dimensions": list(judge_result.get("missing_dimensions") or []),
            "weakest_dimension": weakest_dimension,
            "matched_dimensions": list(judge_result.get("matched_dimensions") or []),
            "citation_urls": [
                str(item.get("url") or "").strip()
                for item in bundle[:12]
                if str(item.get("url") or "").strip()
            ],
            "graph_node": str((graph_plan or {}).get("graph_node") or ""),
            "graph_edges": list((graph_plan or {}).get("graph_edges") or []),
            "branch_type": str((graph_plan or {}).get("branch_type") or ""),
            "branch_subgoal": str((graph_plan or {}).get("branch_subgoal") or ""),
            "scheduler": graph_scheduler,
            "cross_verification": cross_verification,
        },
        "repair_hints": {
            "weakest_dimension": weakest_dimension,
            "missing_dimensions": list(judge_result.get("missing_dimensions") or []),
            "follow_up_dimensions": list(judge_result.get("missing_dimensions") or [])[:2],
            "merge_candidates": list(graph_scheduler.get("merge_candidates") or []),
            "prune_candidates": list(graph_scheduler.get("prune_candidates") or []),
            "next_branch_mode": str(graph_scheduler.get("next_branch_mode") or ""),
            "cross_verification": cross_verification,
            "gap_queue": updated_gap_queue,
            "planning_ops_summary": planning_ops_summary,
        },
        "gap_queue": updated_gap_queue,
        "routeable_output": build_routeable_output(
            goal_case,
            bundle=bundle,
            judge_result=judge_result,
            repair_hints={
                "weakest_dimension": weakest_dimension,
                "missing_dimensions": list(judge_result.get("missing_dimensions") or []),
                "follow_up_dimensions": list(judge_result.get("missing_dimensions") or [])[:2],
                "merge_candidates": list(graph_scheduler.get("merge_candidates") or []),
                "prune_candidates": list(graph_scheduler.get("prune_candidates") or []),
                "next_branch_mode": str(graph_scheduler.get("next_branch_mode") or ""),
                "cross_verification": cross_verification,
                "gap_queue": updated_gap_queue,
                "planning_ops_summary": planning_ops_summary,
            },
        ),
    }
