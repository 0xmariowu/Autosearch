"""Synthesizer stage for research-oriented search execution."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from evaluation_harness import build_bundle, bundle_metrics
from embeddings import semantic_similarity
from evidence.normalize import coerce_evidence_records
from goal_judge import evaluate_goal_bundle
from .bundle import ResearchBundle
from .deep_loop import build_deep_loop_state
from .graph_models import GraphEdge, GraphNode, SearchGraph
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

CLAIM_STOP_WORDS = {
    "the",
    "and",
    "with",
    "that",
    "this",
    "from",
    "into",
    "using",
    "implementation",
    "system",
    "approach",
    "method",
    "results",
    "result",
    "page",
    "report",
    "study",
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
    claim_alignment = _align_claims(bundle)
    contradiction_pairs = list(claim_alignment.get("contradiction_pairs") or [])
    stance_counts = dict(claim_alignment.get("stance_counts") or {"positive": 0, "negative": 0, "neutral": 0})
    contradiction_detected = bool(claim_alignment.get("contradiction_detected"))
    if contradiction_detected:
        consensus_strength = "contested"
    elif int(claim_alignment.get("multi_source_claims", 0) or 0) >= 2 and provider_count >= 3 and domain_count >= 2:
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
        "claim_alignment": list(claim_alignment.get("aligned_claims") or [])[:8],
        "contradiction_clusters": list(claim_alignment.get("contradiction_clusters") or [])[:6],
        "source_dispute_map": dict(claim_alignment.get("source_dispute_map") or {}),
        "query_run_count": len(query_runs),
    }


def _claim_sentences(item: dict[str, Any]) -> list[str]:
    text = " ".join(
        part
        for part in (
            str(item.get("title") or "").strip(),
            str(item.get("extract") or "").strip(),
            str(item.get("body") or "").strip(),
        )
        if part
    )
    if not text:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if len(sentence.strip()) >= 24
    ][:5]


def _claim_terms(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[A-Za-z0-9_\-]{4,}", str(text or "").lower())
        if token not in CLAIM_STOP_WORDS
    ]


def _claim_signature(text: str) -> str:
    terms = _claim_terms(text)
    if not terms:
        return ""
    counts = Counter(terms)
    top_terms = [term for term, _ in counts.most_common(5)]
    return " ".join(sorted(top_terms))


def _query_signature(item: dict[str, Any]) -> str:
    query = str(item.get("query") or "").strip().lower()
    if not query:
        return ""
    terms = re.findall(r"[A-Za-z0-9_\-]{4,}", query)
    if not terms:
        return ""
    counts = Counter(terms)
    return " ".join(sorted(term for term, _ in counts.most_common(4)))


def _topic_signature(item: dict[str, Any], sentence: str) -> str:
    query_signature = _query_signature(item)
    if query_signature:
        return query_signature
    raw = " ".join(
        part
        for part in (
            str(item.get("title") or "").strip(),
            sentence,
        )
        if part
    ).lower()
    terms = [
        token
        for token in re.findall(r"[A-Za-z0-9_\-]{4,}", raw)
        if token not in {"works", "working", "passes", "passed", "verified", "fails", "failed", "failing", "issue", "issues", "stable"}
    ]
    if not terms:
        return ""
    counts = Counter(terms)
    return " ".join(sorted(term for term, _ in counts.most_common(4)))


def _claim_stance(text: str) -> str:
    lowered = str(text or "").lower()
    positive = any(term in lowered for term in POSITIVE_CLAIM_TERMS)
    negative = any(term in lowered for term in NEGATIVE_CLAIM_TERMS)
    if positive and not negative:
        return "positive"
    if negative and not positive:
        return "negative"
    return "neutral"


def _claim_overlap(left: str, right: str) -> float:
    left_terms = set(_claim_terms(left))
    right_terms = set(_claim_terms(right))
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / max(len(left_terms | right_terms), 1)


def _find_claim_cluster(clusters: list[dict[str, Any]], sentence: str, topic_signature: str) -> dict[str, Any] | None:
    signature = _claim_signature(sentence)
    for cluster in clusters:
        representative = str(cluster.get("representative_claim") or "")
        if topic_signature and topic_signature == str(cluster.get("topic_signature") or ""):
            return cluster
        if signature and signature == str(cluster.get("signature") or ""):
            return cluster
        similarity = semantic_similarity(sentence, representative)
        overlap = _claim_overlap(sentence, representative)
        if similarity >= 0.72 or overlap >= 0.45:
            return cluster
    return None


def _align_claims(bundle: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: list[dict[str, Any]] = []
    stance_counts = {"positive": 0, "negative": 0, "neutral": 0}
    source_dispute_map: dict[str, dict[str, Any]] = {}
    for item in list(bundle or []):
        item_source = str(item.get("source") or "").strip()
        item_url = str(item.get("url") or "").strip()
        item_title = str(item.get("title") or "").strip()
        for sentence in _claim_sentences(item):
            stance = _claim_stance(sentence)
            stance_counts[stance] += 1
            topic_signature = _topic_signature(item, sentence)
            cluster = _find_claim_cluster(clusters, sentence, topic_signature)
            if cluster is None:
                cluster = {
                    "cluster_id": f"claim-{len(clusters) + 1}",
                    "signature": _claim_signature(sentence),
                    "topic_signature": topic_signature,
                    "representative_claim": sentence,
                    "stances": Counter(),
                    "sources": [],
                    "urls": [],
                }
                clusters.append(cluster)
            cluster["stances"][stance] += 1
            cluster["sources"].append({
                "source": item_source,
                "url": item_url,
                "title": item_title,
                "stance": stance,
                "claim": sentence,
            })
            if item_url and item_url not in cluster["urls"]:
                cluster["urls"].append(item_url)
            if item_source:
                summary = source_dispute_map.setdefault(
                    item_source,
                    {
                        "positive": 0,
                        "negative": 0,
                        "neutral": 0,
                        "claims": [],
                    },
                )
                summary[stance] += 1
                if sentence not in summary["claims"]:
                    summary["claims"].append(sentence)

    aligned_claims: list[dict[str, Any]] = []
    contradiction_clusters: list[dict[str, Any]] = []
    contradiction_pairs: list[dict[str, Any]] = []
    multi_source_claims = 0
    for cluster in clusters:
        sources = list(cluster.get("sources") or [])
        stances = dict(cluster.get("stances") or {})
        unique_sources = sorted({
            str(item.get("source") or "").strip()
            for item in sources
            if str(item.get("source") or "").strip()
        })
        if len(unique_sources) >= 2:
            multi_source_claims += 1
        payload = {
            "cluster_id": str(cluster.get("cluster_id") or ""),
            "claim": str(cluster.get("representative_claim") or ""),
            "support_count": int(stances.get("positive", 0) or 0),
            "oppose_count": int(stances.get("negative", 0) or 0),
            "neutral_count": int(stances.get("neutral", 0) or 0),
            "sources": unique_sources,
            "source_count": len(unique_sources),
            "urls": list(cluster.get("urls") or [])[:4],
        }
        aligned_claims.append(payload)
        if payload["support_count"] and payload["oppose_count"]:
            contradiction_clusters.append(payload)
            positive_sources = [item for item in sources if str(item.get("stance") or "") == "positive"]
            negative_sources = [item for item in sources if str(item.get("stance") or "") == "negative"]
            for left in positive_sources[:2]:
                for right in negative_sources[:2]:
                    contradiction_pairs.append({
                        "claim": payload["claim"],
                        "left_source": str(left.get("source") or ""),
                        "left_url": str(left.get("url") or ""),
                        "right_source": str(right.get("source") or ""),
                        "right_url": str(right.get("url") or ""),
                    })
    contradiction_detected = bool(contradiction_clusters)
    return {
        "aligned_claims": sorted(
            aligned_claims,
            key=lambda item: (int(item.get("support_count", 0) or 0) + int(item.get("oppose_count", 0) or 0), int(item.get("source_count", 0) or 0)),
            reverse=True,
        ),
        "contradiction_clusters": contradiction_clusters,
        "contradiction_pairs": contradiction_pairs,
        "source_dispute_map": source_dispute_map,
        "stance_counts": stance_counts,
        "contradiction_detected": contradiction_detected,
        "multi_source_claims": multi_source_claims,
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
    graph_node_id = str((graph_plan or {}).get("graph_node") or "")
    graph_edges = [
        GraphEdge(
            source=str(item.get("from") or ""),
            target=str(item.get("to") or ""),
            kind=str(item.get("kind") or "branch"),
            metadata={k: v for k, v in dict(item).items() if k not in {"from", "to", "kind"}},
        )
        for item in list((graph_plan or {}).get("graph_edges") or [])
    ]
    graph_nodes = []
    if graph_node_id:
        graph_nodes.append(
            GraphNode(
                node_id=graph_node_id,
                label=graph_node_id,
                node_type="research_branch",
                branch_type=str((graph_plan or {}).get("branch_type") or ""),
                branch_subgoal=str((graph_plan or {}).get("branch_subgoal") or ""),
                priority=int(((graph_plan or {}).get("branch_depth", 0) or 0)),
                metadata={"branch_targets": list((graph_plan or {}).get("branch_targets") or [])},
            )
        )
    search_graph = SearchGraph(
        goal_id=str(goal_case.get("id") or "goal"),
        bundle_id=str(research_bundle.bundle_id),
        nodes=graph_nodes,
        edges=graph_edges,
        scheduler=graph_scheduler,
        cross_verification=cross_verification,
    )
    deep_loop_state = build_deep_loop_state(
        mode=str(goal_case.get("mode") or "balanced"),
        graph_plan=graph_plan,
        bundle=bundle,
        judge_result=judge_result,
    )
    routeable_output = build_routeable_output(
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
    )
    return {
        "bundle": bundle,
        "research_bundle": research_bundle.to_dict(),
        "judge_result": judge_result,
        "harness_metrics": metrics,
        "search_graph": {
            **search_graph.to_dict(),
            "bundle_size": len(bundle),
            "missing_dimensions": list(judge_result.get("missing_dimensions") or []),
            "weakest_dimension": weakest_dimension,
            "matched_dimensions": list(judge_result.get("matched_dimensions") or []),
            "citation_urls": [
                str(item.get("url") or "").strip()
                for item in bundle[:12]
                if str(item.get("url") or "").strip()
            ],
            "graph_node": graph_node_id,
            "graph_edges": [item.to_dict() for item in graph_edges],
            "branch_type": str((graph_plan or {}).get("branch_type") or ""),
            "branch_subgoal": str((graph_plan or {}).get("branch_subgoal") or ""),
            "deep_loop": deep_loop_state.to_dict(),
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
        "routeable_output": routeable_output,
    }
