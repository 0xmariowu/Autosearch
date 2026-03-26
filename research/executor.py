"""Executor stage for research-oriented search execution."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from evidence.normalize import coerce_evidence_record, coerce_evidence_records
from evidence_index import search_evidence
from goal_services import (
    platforms_for_provider_mix,
    restrict_query_to_provider_mix,
    sample_findings,
    search_query,
)
from query_dedup import dedup_query_specs
from search_mesh.registry import classify_query, provider_names_for_classification

DEEP_GENERIC_TERMS = {
    "implementation",
    "details",
    "report",
    "validation",
    "release",
    "query",
    "issue",
    "issues",
    "dataset",
    "code",
    "source",
    "guide",
    "using",
    "with",
}


def _query_role_terms(text: str) -> set[str]:
    lowered = str(text or "").lower()
    roles: set[str] = set()
    if any(term in lowered for term in ("repo", "repository", "sdk", "library", "tool")):
        roles.add("repos")
    if any(term in lowered for term in ("issue", "error", "bug", "failure", "incident", "postmortem")):
        roles.add("discussion")
    if any(term in lowered for term in ("code", "implementation", "source", "diff", "patch")):
        roles.add("code")
    if any(term in lowered for term in ("dataset", "benchmark", "trajectory", "eval set")):
        roles.add("datasets")
    if any(term in lowered for term in ("tweet", "twitter", "xreach", "social")):
        roles.add("social")
    return roles


def _platforms_for_intent(
    query: dict[str, Any],
    default_platforms: list[dict[str, Any]],
    *,
    provider_mix: list[str],
    backend_roles: dict[str, list[str]] | None,
    plan_role: str,
) -> list[dict[str, Any]]:
    effective_platforms = platforms_for_provider_mix(default_platforms, provider_mix)
    explicit_platforms = list((query or {}).get("platforms") or [])
    if explicit_platforms:
        explicit_names = {
            str((platform or {}).get("name") or "").strip()
            for platform in explicit_platforms
            if str((platform or {}).get("name") or "").strip()
        }
        if not explicit_names:
            return effective_platforms
        allowed_names = {
            str((platform or {}).get("name") or "").strip()
            for platform in effective_platforms
            if str((platform or {}).get("name") or "").strip()
        }
        filtered = [
            dict(platform)
            for platform in explicit_platforms
            if str((platform or {}).get("name") or "").strip() in allowed_names
        ]
        return filtered or effective_platforms
    roles = dict(backend_roles or {})
    selected: list[str] = []
    classification = classify_query(str(query.get("text") or ""), plan_role=plan_role)
    if plan_role == "broad_recall":
        selected.extend(list(roles.get("breadth") or []))
    for role_name in sorted(_query_role_terms(query.get("text") or "")):
        selected.extend(list(roles.get(role_name) or []))
    classified_names = provider_names_for_classification(classification)
    if selected and classified_names:
        gated = [name for name in selected if name in classified_names]
        if gated:
            selected = gated
    elif classified_names:
        selected.extend(classified_names)
    if not selected:
        return effective_platforms
    seen: set[str] = set()
    narrowed = []
    for platform in effective_platforms:
        name = str(platform.get("name") or "")
        if name in selected and name not in seen:
            narrowed.append(dict(platform))
            seen.add(name)
    return narrowed or effective_platforms


def _intent_query_spec(query: dict[str, Any], provider_mix: list[str]) -> dict[str, Any]:
    if str(query.get("record_type") or "") == "evidence":
        text = " ".join(
            part
            for part in (
                str(query.get("query") or "").strip(),
                str(query.get("summary") or "").strip(),
                str(query.get("title") or "").strip(),
            )
            if part
        ).strip()
        return restrict_query_to_provider_mix({"text": text, "platforms": []}, provider_mix)
    return restrict_query_to_provider_mix(query, provider_mix)


def _cross_verification_intents(
    decision: dict[str, Any] | None,
    *,
    tried: set[str],
) -> list[dict[str, Any]]:
    payload = dict(decision or {})
    if not bool(payload.get("cross_verify")):
        return []
    intents: list[dict[str, Any]] = []
    for query in list(payload.get("cross_verification_queries") or []):
        spec = {
            "text": str((query or {}).get("text") or "").strip(),
            "platforms": list((query or {}).get("platforms") or []),
        }
        if not spec["text"]:
            continue
        if str(spec) in tried or spec in intents:
            continue
        intents.append(spec)
    return intents


def _execution_query_key(
    query: dict[str, Any],
    *,
    intent_platforms: list[dict[str, Any]],
    query_key_fn: Any | None,
) -> str:
    base = str(query_key_fn(query)) if query_key_fn is not None else str(query)
    explicit_platforms = list((query or {}).get("platforms") or [])
    if explicit_platforms:
        return base
    provider_names = [
        str((platform or {}).get("name") or "").strip()
        for platform in list(intent_platforms or [])
        if str((platform or {}).get("name") or "").strip()
    ]
    return f"{base}::providers={provider_names!r}"


def _deep_reason_terms(findings: list[dict[str, Any]], *, limit: int = 4) -> list[str]:
    counts: Counter[str] = Counter()
    for item in list(findings or []):
        haystack = " ".join(
            part
            for part in (
                str(item.get("title") or "").strip(),
                str(item.get("extract") or "").strip(),
                str(item.get("acquired_text") or "").strip(),
                str(item.get("body") or "").strip(),
            )
            if part
        ).lower()
        for token in re.findall(r"[A-Za-z0-9_\-]{5,}", haystack):
            if token in DEEP_GENERIC_TERMS:
                continue
            counts[token] += 1
    return [term for term, _ in counts.most_common(limit)]


def _deep_followup_queries(
    query: dict[str, Any],
    findings: list[dict[str, Any]],
    *,
    tried: set[str],
    max_queries: int = 1,
) -> list[dict[str, Any]]:
    base_text = str((query or {}).get("text") or "").strip()
    if not base_text:
        return []
    reason_terms = _deep_reason_terms(findings)
    if not reason_terms:
        return []
    followups: list[dict[str, Any]] = []
    suffixes = ["implementation details", "operational proof", "release blocker"]
    for suffix in suffixes:
        spec = {"text": f"{base_text} {' '.join(reason_terms[:2])} {suffix}".strip(), "platforms": []}
        if str(spec) in tried or spec in followups:
            continue
        followups.append(spec)
        if len(followups) >= max_queries:
            break
    return followups


def execute_research_plan(
    plan: dict[str, Any],
    *,
    default_platforms: list[dict[str, Any]],
    provider_mix: list[str] | None = None,
    backend_roles: dict[str, list[str]] | None = None,
    sampling_policy: dict[str, Any] | None = None,
    tried_queries: set[str] | None = None,
    query_key_fn: Any | None = None,
    local_evidence_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    decision = dict(plan.get("decision") or {})
    effective_provider_mix = list(decision.get("provider_mix") or provider_mix or [])
    effective_platforms = platforms_for_provider_mix(default_platforms, effective_provider_mix)
    query_runs: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    deep_steps: list[dict[str, Any]] = []
    query_keys: list[str] = []
    tried = set(tried_queries or set())
    intents = list(plan.get("intents") or [])
    intents.extend(_cross_verification_intents(decision, tried=tried))
    intents = dedup_query_specs(intents, threshold=0.88)
    local_records = coerce_evidence_records(local_evidence_records or plan.get("local_evidence_records") or [])
    effective_sampling_policy = {
        **dict(sampling_policy or {}),
        **dict(decision.get("sampling_policy") or {}),
        **dict(decision.get("acquisition_policy") or {}),
        **dict(decision.get("evidence_policy") or {}),
    }
    effective_backend_roles = dict(decision.get("backend_roles") or backend_roles or {})
    local_limit = int(effective_sampling_policy.get("local_evidence_limit", 3) or 3)
    plan_role = str(plan.get("role") or "")
    mode = str(decision.get("mode") or plan.get("mode") or "balanced")
    verification_query_count = 0
    remaining_intents = list(intents)
    deep_followup_budget = 1 if mode == "deep" else 0
    intent_index = 0
    while intent_index < len(remaining_intents):
        query = remaining_intents[intent_index]
        intent_index += 1
        raw_query = (
            coerce_evidence_record(query)
            if isinstance(query, dict) and str(query.get("record_type") or "") == "evidence"
            else query
        )
        effective_query = _intent_query_spec(raw_query, effective_provider_mix)
        intent_platforms = _platforms_for_intent(
            effective_query,
            effective_platforms,
            provider_mix=effective_provider_mix,
            backend_roles=effective_backend_roles,
            plan_role=plan_role,
        )
        effective_query = _intent_query_spec(
            effective_query,
            [str(item.get("name") or "") for item in intent_platforms],
        )
        key = _execution_query_key(
            effective_query,
            intent_platforms=intent_platforms,
            query_key_fn=query_key_fn,
        )
        if key in tried:
            continue
        query_keys.append(key)
        local_hits = coerce_evidence_records(
            search_evidence(local_records, str(effective_query.get("text") or ""), limit=local_limit)
        )
        findings.extend(local_hits)
        deep_steps.append({
            "kind": "search",
            "summary": f"searched: {effective_query.get('text', '')}",
            "metadata": {"provider_count": len(intent_platforms)},
        })
        run = search_query(
            effective_query,
            intent_platforms,
            sampling_policy=effective_sampling_policy,
        )
        normalized_findings = coerce_evidence_records(run["findings"])
        if effective_query in _cross_verification_intents(decision, tried=set()):
            verification_query_count += 1
        query_runs.append({
            "query": run["query"],
            "query_spec": run["query_spec"],
            "baseline_score": run["baseline_score"],
            "finding_count": len(normalized_findings),
            "local_evidence_count": len(local_hits),
            "sample_findings": sample_findings(normalized_findings, limit=5),
        })
        findings.extend(normalized_findings)
        deep_steps.append({
            "kind": "read",
            "summary": f"read {len(normalized_findings) + len(local_hits)} evidence records",
            "metadata": {
                "finding_count": len(normalized_findings),
                "local_evidence_count": len(local_hits),
            },
        })
        if mode == "deep":
            reason_terms = _deep_reason_terms(normalized_findings or local_hits)
            deep_steps.append({
                "kind": "reason",
                "summary": "reasoned over acquired evidence",
                "metadata": {"reason_terms": reason_terms[:6]},
            })
            if deep_followup_budget > 0:
                followups = _deep_followup_queries(
                    effective_query,
                    normalized_findings or local_hits,
                    tried=tried | set(query_keys),
                    max_queries=1,
                )
                for followup in followups:
                    remaining_intents.append(followup)
                if followups:
                    deep_followup_budget -= len(followups)
    return {
        "label": str(plan.get("label") or "plan"),
        "queries": remaining_intents,
        "role": str(plan.get("role") or ""),
        "branch_type": str(plan.get("branch_type") or ""),
        "branch_subgoal": str(plan.get("branch_subgoal") or ""),
        "stage": str(plan.get("stage") or ""),
        "graph_node": str(plan.get("graph_node") or ""),
        "graph_edges": list(plan.get("graph_edges") or []),
        "branch_targets": list(plan.get("branch_targets") or []),
        "branch_depth": int(plan.get("branch_depth", 0) or 0),
        "decision": decision,
        "planning_ops": list(plan.get("planning_ops") or []),
        "cross_verification": {
            "enabled": bool(decision.get("cross_verify")),
            "verification_query_count": verification_query_count,
        },
        "deep_steps": deep_steps,
        "local_evidence_hits": len(local_records),
        "query_keys": query_keys,
        "query_runs": query_runs,
        "findings": coerce_evidence_records(findings),
    }
