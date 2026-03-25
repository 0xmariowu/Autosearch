#!/usr/bin/env python3
"""Internal goal-loop services shared by interface and runtime modules."""

from __future__ import annotations

import json
from typing import Any

from engine import PlatformConnector, Scorer
from source_capability import get_source_decision

__all__ = [
    "available_platforms",
    "merge_findings",
    "normalize_query_spec",
    "query_key",
    "query_text",
    "replay_queries",
    "sample_findings",
    "search_query",
]


def normalize_query_spec(query: Any) -> dict[str, Any]:
    if isinstance(query, dict):
        return {
            "text": str(query.get("text") or "").strip(),
            "platforms": list(query.get("platforms") or []),
        }
    return {"text": str(query or "").strip(), "platforms": []}


def query_key(query: Any) -> str:
    spec = normalize_query_spec(query)
    return json.dumps(spec, ensure_ascii=False, sort_keys=True)


def query_text(query: Any) -> str:
    return normalize_query_spec(query).get("text", "")


def available_platforms(goal_case: dict[str, Any], capability_report: dict[str, Any]) -> list[dict[str, Any]]:
    platforms: list[dict[str, Any]] = []
    for name in goal_case.get("providers", []):
        decision = get_source_decision(capability_report, name)
        if decision["should_skip"]:
            continue
        if name == "github_repos":
            platforms.append({"name": name, "limit": 5, "min_stars": 20})
        elif name == "github_issues":
            platforms.append({"name": name, "limit": 5})
        elif name == "twitter_xreach":
            platforms.append({"name": name, "limit": 10})
        else:
            platforms.append({"name": name, "limit": 5})
    return platforms


def _query_platforms(query: Any, default_platforms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spec = normalize_query_spec(query)
    if spec["platforms"]:
        return [dict(item) for item in spec["platforms"] if item.get("name")]
    return [dict(item) for item in default_platforms]


def _query_terms(text: str) -> set[str]:
    return {term for term in text.lower().split() if len(term) >= 4}


def _result_relevance(query: str, result: Any) -> tuple[int, int]:
    terms = _query_terms(query)
    haystack = " ".join([
        str(getattr(result, "title", "") or ""),
        str(getattr(result, "body", "") or ""),
        str(getattr(result, "url", "") or ""),
        str(getattr(result, "source", "") or ""),
    ]).lower()
    overlap = sum(1 for term in terms if term in haystack)
    return overlap, int(getattr(result, "eng", 0) or 0)


def _sampling_config(sampling_policy: dict[str, Any] | None) -> dict[str, Any]:
    policy = dict(sampling_policy or {})
    bundle_cap = int(policy.get("bundle_per_query_cap", 5) or 5)
    return {
        "rank_by_relevance": bool(policy.get("rank_by_relevance", True)),
        "per_query_findings_cap": int(policy.get("per_query_findings_cap", max(bundle_cap * 3, 5)) or max(bundle_cap * 3, 5)),
        "bundle_per_query_cap": bundle_cap,
    }


def search_query(
    query: Any,
    default_platforms: list[dict[str, Any]],
    sampling_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_str = query_text(query)
    platforms = _query_platforms(query, default_platforms)
    sampling = _sampling_config(sampling_policy)
    scorer = Scorer()
    all_results = []
    findings: list[dict[str, Any]] = []
    for platform in platforms:
        platform_query = str(platform.get("query") or query_str)
        platform_config = dict(platform)
        platform_config.pop("query", None)
        outcome = PlatformConnector.search(platform_config, platform_query)
        all_results.extend(outcome.results)
    _, raw_score, new_results = scorer.score_results(all_results)
    if sampling["rank_by_relevance"]:
        ranked_results = sorted(
            new_results,
            key=lambda result: _result_relevance(query_str, result),
            reverse=True,
        )
    else:
        ranked_results = list(new_results)
    positive_ranked = [result for result in ranked_results if _result_relevance(query_str, result)[0] > 0]
    selected_results = positive_ranked or ranked_results
    for result in selected_results[: sampling["per_query_findings_cap"]]:
        findings.append({
            "title": result.title,
            "url": result.url,
            "body": result.body,
            "source": result.source,
            "query": query_str,
        })
    return {
        "query": query_str,
        "query_spec": normalize_query_spec(query),
        "baseline_score": raw_score,
        "findings": findings,
    }


def merge_findings(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in list(existing) + list(incoming):
        url = str(item.get("url") or "")
        key = url or str(item.get("title") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def sample_findings(items: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    return [
        {
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "source": str(item.get("source") or ""),
            "query": str(item.get("query") or ""),
            "body": str(item.get("body") or "")[:220],
        }
        for item in items[:limit]
    ]


def replay_queries(
    queries: list[dict[str, Any]],
    platforms: list[dict[str, Any]],
    sampling_policy: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    query_runs: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for query in queries:
        run = search_query(query, platforms, sampling_policy=sampling_policy)
        query_runs.append({
            "query": run["query"],
            "query_spec": run["query_spec"],
            "baseline_score": run["baseline_score"],
            "finding_count": len(run["findings"]),
            "sample_findings": sample_findings(run["findings"], limit=5),
        })
        findings.extend(run["findings"])
    return query_runs, merge_findings([], findings)
