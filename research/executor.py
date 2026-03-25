"""Executor stage for research-oriented search execution."""

from __future__ import annotations

from typing import Any

from goal_services import (
    platforms_for_provider_mix,
    restrict_query_to_provider_mix,
    sample_findings,
    search_query,
)


def execute_research_plan(
    plan: dict[str, Any],
    *,
    default_platforms: list[dict[str, Any]],
    provider_mix: list[str] | None = None,
    sampling_policy: dict[str, Any] | None = None,
    tried_queries: set[str] | None = None,
    query_key_fn: Any | None = None,
) -> dict[str, Any]:
    effective_provider_mix = list(provider_mix or [])
    effective_platforms = platforms_for_provider_mix(default_platforms, effective_provider_mix)
    query_runs: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    query_keys: list[str] = []
    tried = set(tried_queries or set())
    intents = list(plan.get("intents") or [])
    for query in intents:
        effective_query = restrict_query_to_provider_mix(query, effective_provider_mix)
        if query_key_fn is not None:
            key = str(query_key_fn(effective_query))
            if key in tried:
                continue
            query_keys.append(key)
        run = search_query(
            effective_query,
            effective_platforms,
            sampling_policy=sampling_policy,
        )
        query_runs.append({
            "query": run["query"],
            "query_spec": run["query_spec"],
            "baseline_score": run["baseline_score"],
            "finding_count": len(run["findings"]),
            "sample_findings": sample_findings(run["findings"], limit=5),
        })
        findings.extend(run["findings"])
    return {
        "label": str(plan.get("label") or "plan"),
        "queries": intents,
        "query_keys": query_keys,
        "query_runs": query_runs,
        "findings": findings,
    }
