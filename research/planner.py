"""Planner stage for research-oriented search execution."""

from __future__ import annotations

from collections import Counter
from typing import Any


def _current_round_role(active_program: dict[str, Any], round_history: list[dict[str, Any]]) -> str:
    roles = [str(item or "").strip() for item in list(active_program.get("round_roles") or []) if str(item or "").strip()]
    if not roles:
        return str(active_program.get("current_role") or "broad_recall")
    if round_history:
        return roles[min(len(round_history), len(roles) - 1)]
    return roles[0]


def _anchor_tokens(local_evidence_records: list[dict[str, Any]] | None, *, limit: int = 4) -> list[str]:
    counts: Counter[str] = Counter()
    for item in list(local_evidence_records or []):
        title = str(item.get("title") or "").lower()
        for token in title.split():
            token = token.strip(".,:;()[]{}")
            if len(token) < 5:
                continue
            if token in {"https", "http", "github", "issue", "issues", "about", "using"}:
                continue
            counts[token] += 1
    return [token for token, _ in counts.most_common(limit)]


def _repair_terms(judge_result: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for item in list(judge_result.get("missing_dimensions") or [])[:3]:
        text = str(item or "").replace("_", " ").strip()
        if text:
            terms.append(text)
    weakest = ""
    scores = dict(judge_result.get("dimension_scores") or {})
    if scores:
        weakest = min(scores.keys(), key=lambda key: int(scores.get(key, 0) or 0))
    weakest = weakest.replace("_", " ").strip()
    if weakest and weakest not in terms:
        terms.insert(0, weakest)
    return terms[:3]


def _augment_queries(
    queries: list[dict[str, Any]],
    *,
    local_evidence_records: list[dict[str, Any]] | None,
    judge_result: dict[str, Any],
    tried_queries: set[str],
    max_queries: int,
) -> list[dict[str, Any]]:
    augmented = list(queries)
    anchors = _anchor_tokens(local_evidence_records)
    repairs = _repair_terms(judge_result)
    for anchor in anchors:
        for repair in repairs:
            query = {"text": f"{anchor} {repair}".strip(), "platforms": []}
            key = str(query)
            if key in tried_queries:
                continue
            if query not in augmented:
                augmented.append(query)
            if len(augmented) >= max_queries:
                return augmented[:max_queries]
    return augmented[:max_queries]


def _follow_up_queries(
    *,
    local_evidence_records: list[dict[str, Any]] | None,
    judge_result: dict[str, Any],
    max_queries: int,
    tried_queries: set[str],
) -> list[dict[str, Any]]:
    anchors = _anchor_tokens(local_evidence_records, limit=6)
    repairs = _repair_terms(judge_result)
    follow_ups: list[dict[str, Any]] = []
    for repair in repairs:
        for anchor in anchors:
            spec = {"text": f"{anchor} {repair} implementation".strip(), "platforms": []}
            if str(spec) in tried_queries or spec in follow_ups:
                continue
            follow_ups.append(spec)
            if len(follow_ups) >= max_queries:
                return follow_ups
    return follow_ups


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
    local_evidence_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    current_role = _current_round_role(active_program, round_history)
    local_evidence_records = list(local_evidence_records or [])
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
    previous_node = str((round_history[-1] or {}).get("graph_node") or "") if round_history else ""
    follow_up_candidates = _follow_up_queries(
        local_evidence_records=local_evidence_records,
        judge_result=judge_result,
        max_queries=max_queries,
        tried_queries=tried_queries,
    )
    for index, plan in enumerate(list(plans or []), start=1):
        queries = _augment_queries(
            list(plan.get("queries") or []),
            local_evidence_records=local_evidence_records if current_role != "broad_recall" else [],
            judge_result=judge_result,
            tried_queries=tried_queries,
            max_queries=max_queries,
        )
        role = str(plan.get("role") or current_role or "broad_recall")
        graph_node = f"{role}-{index}"
        branch_targets = _repair_terms(judge_result)
        normalized.append({
            "label": str(plan.get("label") or "plan"),
            "queries": queries,
            "intents": queries,
            "role": role,
            "stage": "repair" if role != "broad_recall" else "breadth",
            "graph_node": graph_node,
            "graph_edges": [{"from": previous_node, "to": graph_node}] if previous_node else [],
            "branch_targets": branch_targets,
            "program_overrides": dict(plan.get("program_overrides") or {}),
            "local_evidence_records": local_evidence_records,
        })
    if follow_up_candidates and len(normalized) < max(plan_count, 1):
        graph_node = f"followup-{len(normalized) + 1}"
        normalized.append({
            "label": "graph-followup",
            "queries": follow_up_candidates[:max_queries],
            "intents": follow_up_candidates[:max_queries],
            "role": "graph_followup",
            "stage": "followup",
            "graph_node": graph_node,
            "graph_edges": [{"from": previous_node, "to": graph_node, "kind": "follow_up"}] if previous_node else [],
            "branch_targets": _repair_terms(judge_result),
            "program_overrides": {"current_role": "dimension_repair"},
            "local_evidence_records": local_evidence_records,
        })
    return normalized
