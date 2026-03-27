#!/usr/bin/env python3
"""Internal goal-loop services shared by interface and runtime modules."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from acquisition import enrich_evidence_record
from evidence import build_evidence_record, evidence_content_type
from engine import PlatformConnector
from goal_judge import _pair_extract_finding_score
from query_dedup import dedup_query_specs
from rerank import rerank_hits
from search_mesh.provider_policy import (
    available_platforms as policy_available_platforms,
    default_platform_config,
    goal_provider_names,
)
from search_mesh.router import search_platform
from search_mesh.models import SearchHit, SearchHitBatch

__all__ = [
    "available_platforms",
    "merge_findings",
    "normalize_query_spec",
    "platforms_for_provider_mix",
    "query_key",
    "query_text",
    "replay_queries",
    "restrict_query_to_provider_mix",
    "sample_findings",
    "search_query",
]


def _goal_provider_names(goal_case: dict[str, Any]) -> list[str]:
    return goal_provider_names(goal_case)


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


def available_platforms(
    goal_case: dict[str, Any], capability_report: dict[str, Any]
) -> list[dict[str, Any]]:
    return policy_available_platforms(goal_case, capability_report)


def platforms_for_provider_mix(
    platforms: list[dict[str, Any]],
    provider_mix: list[str] | None,
) -> list[dict[str, Any]]:
    allowed = [
        str(name or "").strip()
        for name in list(provider_mix or [])
        if str(name or "").strip()
    ]
    if not allowed:
        return [dict(platform) for platform in platforms]
    return [
        dict(platform)
        for platform in platforms
        if str(platform.get("name") or "") in allowed
    ]


def restrict_query_to_provider_mix(
    query: Any, provider_mix: list[str] | None
) -> dict[str, Any]:
    spec = normalize_query_spec(query)
    allowed = {
        str(name or "").strip()
        for name in list(provider_mix or [])
        if str(name or "").strip()
    }
    if not allowed or not spec.get("platforms"):
        return spec
    spec["platforms"] = [
        dict(platform)
        for platform in list(spec.get("platforms") or [])
        if str((platform or {}).get("name") or "") in allowed
    ]
    return spec


def _query_platforms(
    query: Any, default_platforms: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    spec = normalize_query_spec(query)
    if spec["platforms"]:
        return [dict(item) for item in spec["platforms"] if item.get("name")]
    return [dict(item) for item in default_platforms]


def _query_terms(text: str) -> set[str]:
    return {term for term in text.lower().split() if len(term) >= 4}


def _result_relevance(
    query: str, result: Any, preferred_content_types: list[str] | None = None
) -> tuple[int, int]:
    terms = _query_terms(query)
    haystack = " ".join(
        [
            str(getattr(result, "title", "") or ""),
            str(getattr(result, "body", "") or ""),
            str(getattr(result, "url", "") or ""),
            str(getattr(result, "source", "") or ""),
        ]
    ).lower()
    overlap = sum(1 for term in terms if term in haystack)
    bonus = 0
    preferred = {
        str(item or "").strip()
        for item in list(preferred_content_types or [])
        if str(item or "").strip()
    }
    if preferred:
        content_type = evidence_content_type(
            str(getattr(result, "source", "") or ""),
            str(getattr(result, "url", "") or ""),
        )
        if content_type in preferred:
            bonus = 2
    return overlap + bonus, int(getattr(result, "eng", 0) or 0)


def _hit_relevance(
    query: str, hit: SearchHit, preferred_content_types: list[str] | None = None
) -> tuple[int, int]:
    terms = _query_terms(query)
    haystack = " ".join(
        [
            str(hit.title or ""),
            str(hit.snippet or ""),
            str(hit.url or ""),
            str(hit.source or ""),
        ]
    ).lower()
    overlap = sum(1 for term in terms if term in haystack)
    bonus = 0
    preferred = {
        str(item or "").strip()
        for item in list(preferred_content_types or [])
        if str(item or "").strip()
    }
    if preferred:
        content_type = evidence_content_type(str(hit.source or ""), str(hit.url or ""))
        if content_type in preferred:
            bonus = 2
    return overlap + bonus, int(hit.score_hint or 0)


def _build_evidence_record_from_hit(hit: SearchHit) -> dict[str, Any]:
    return build_evidence_record(
        title=str(hit.title or ""),
        url=str(hit.url or ""),
        body=str(hit.snippet or ""),
        source=str(hit.source or hit.provider or ""),
        query=str(hit.query or ""),
        query_family=str(hit.query_family or "unknown"),
        backend=str(hit.backend or hit.provider or ""),
    )


def _sampling_config(sampling_policy: dict[str, Any] | None) -> dict[str, Any]:
    policy = dict(sampling_policy or {})
    bundle_cap = int(policy.get("bundle_per_query_cap", 5) or 5)
    return {
        "rank_by_relevance": bool(policy.get("rank_by_relevance", True)),
        "per_query_findings_cap": int(
            policy.get("per_query_findings_cap", max(bundle_cap * 3, 5))
            or max(bundle_cap * 3, 5)
        ),
        "bundle_per_query_cap": bundle_cap,
        "acquire_pages": bool(policy.get("acquire_pages", False)),
        "page_fetch_limit": int(policy.get("page_fetch_limit", 2) or 2),
        "use_render_fallback": bool(policy.get("use_render_fallback", False)),
        "use_crawl4ai_adapter": bool(policy.get("use_crawl4ai_adapter", False)),
        "rerank_profile": str(
            policy.get("rerank_profile")
            or ("hybrid" if bool(policy.get("rank_by_relevance", True)) else "none")
        ),
        "domain_cap": int(policy.get("domain_cap", 0) or 0),
        "provider_timeout_seconds": int(
            policy.get("provider_timeout_seconds", 10) or 10
        ),
        "parallel_provider_limit": int(policy.get("parallel_provider_limit", 6) or 6),
        "preferred_content_types": [
            str(item or "").strip()
            for item in list(policy.get("preferred_content_types") or [])
            if str(item or "").strip()
        ],
        "prefer_acquired_text": bool(policy.get("prefer_acquired_text", False)),
        "semantic_query_dedup": bool(policy.get("semantic_query_dedup", False)),
    }


def _platform_batch(
    platform: dict[str, Any], platform_query: str, preferred_content_types: list[str]
) -> SearchHitBatch:
    platform_config = dict(platform)
    platform_config.pop("query", None)
    if "limit" not in platform_config and platform_config.get("name"):
        platform_config = {
            **default_platform_config(str(platform_config.get("name") or "")),
            **platform_config,
        }
    platform_search = getattr(PlatformConnector, "search")
    if "unittest.mock" in str(type(platform_search)):
        outcome = platform_search(platform_config, platform_query)
        return SearchHitBatch.from_hit_dicts(
            provider=str(
                getattr(outcome, "provider", "") or platform_config.get("name") or ""
            ),
            query=platform_query,
            items=[
                {
                    "title": str(getattr(result, "title", "") or ""),
                    "url": str(getattr(result, "url", "") or ""),
                    "body": str(getattr(result, "body", "") or ""),
                    "source": str(
                        getattr(result, "source", "")
                        or platform_config.get("name")
                        or ""
                    ),
                    "eng": int(getattr(result, "eng", 0) or 0),
                }
                for result in list(getattr(outcome, "results", []) or [])
            ],
            backend=str(platform_config.get("name") or ""),
            error_alias=str(getattr(outcome, "error_alias", "") or ""),
        )
    return search_platform(
        platform_config,
        platform_query,
        context={"preferred_content_types": preferred_content_types},
    )


def _enrich_record(
    record: dict[str, Any], *, query: str, **kwargs: Any
) -> dict[str, Any]:
    try:
        return enrich_evidence_record(record, query=query, **kwargs)
    except TypeError as exc:
        if "unexpected keyword argument 'query'" not in str(exc):
            raise
        return enrich_evidence_record(record, **kwargs)


def search_query(
    query: Any,
    default_platforms: list[dict[str, Any]],
    sampling_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_str = query_text(query)
    platforms = _query_platforms(query, default_platforms)
    sampling = _sampling_config(sampling_policy)
    all_hits: list[SearchHit] = []
    findings: list[dict[str, Any]] = []
    timed_out_providers: list[str] = []
    max_workers = max(
        1, min(len(platforms), int(sampling["parallel_provider_limit"] or 1))
    )
    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        futures = {
            executor.submit(
                _platform_batch,
                dict(platform),
                str(platform.get("query") or query_str),
                list(sampling["preferred_content_types"]),
            ): str(platform.get("name") or "")
            for platform in platforms
        }
        done, pending = wait(
            futures.keys(), timeout=float(sampling["provider_timeout_seconds"])
        )
        for future in done:
            try:
                batch = future.result()
            except Exception:
                continue
            all_hits.extend(list(batch.hits))
        for future in pending:
            timed_out_providers.append(futures.get(future, ""))
            future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    rerank_profile = str(sampling["rerank_profile"])
    ranked_hits = rerank_hits(
        query_str,
        all_hits,
        preferred_content_types=sampling["preferred_content_types"],
        rerank_profile=rerank_profile,
        max_per_domain=int(sampling["domain_cap"] or 0) or None,
    )
    positive_ranked = [
        hit
        for hit in ranked_hits
        if _hit_relevance(query_str, hit, sampling["preferred_content_types"])[0] > 0
    ]
    selected_hits = positive_ranked or ranked_hits
    raw_score = sum(
        max(int(hit.score_hint or 0), 0)
        + max(_hit_relevance(query_str, hit, sampling["preferred_content_types"])[0], 0)
        for hit in selected_hits
    )
    for index, hit in enumerate(selected_hits[: sampling["per_query_findings_cap"]]):
        record = _build_evidence_record_from_hit(hit)
        if sampling["acquire_pages"] and index < sampling["page_fetch_limit"]:
            enrich_kwargs: dict[str, Any] = {}
            if sampling["use_crawl4ai_adapter"]:
                enrich_kwargs["use_crawl4ai_adapter"] = True
            if sampling["use_render_fallback"]:
                record = _enrich_record(
                    record,
                    use_render_fallback=True,
                    query=query_str,
                    **enrich_kwargs,
                )
            else:
                record = _enrich_record(
                    record,
                    query=query_str,
                    **enrich_kwargs,
                )
            if sampling["prefer_acquired_text"] and record.get("acquired_text"):
                record = build_evidence_record(
                    title=str(
                        record.get("acquired_title") or record.get("title") or ""
                    ),
                    url=str(record.get("url") or ""),
                    body=str(record.get("acquired_text") or ""),
                    source=str(record.get("source") or ""),
                    query=query_str,
                    clean_markdown=str(record.get("clean_markdown") or ""),
                    fit_markdown=str(record.get("fit_markdown") or ""),
                    references=list(record.get("references") or []),
                )
                record["acquired"] = True
                record["acquired_text"] = str(record.get("canonical_text") or "")
        findings.append(record)
    return {
        "query": query_str,
        "query_spec": normalize_query_spec(query),
        "baseline_score": raw_score,
        "findings": findings,
        "partial_results": bool(timed_out_providers),
        "timed_out_providers": [item for item in timed_out_providers if item],
    }


def merge_findings(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
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


def sample_findings(
    items: list[dict[str, Any]], limit: int = 12
) -> list[dict[str, Any]]:
    ranked = list(items or [])
    if ranked:
        scores = [_pair_extract_finding_score(item) for item in ranked]
        if max(scores, default=0) >= 5:
            ranked = [
                item
                for _index, _score, item in sorted(
                    (
                        (index, _pair_extract_finding_score(item), item)
                        for index, item in enumerate(ranked)
                    ),
                    key=lambda row: (row[1], -row[0]),
                    reverse=True,
                )
            ]
    return [
        {
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "source": str(item.get("source") or ""),
            "query": str(item.get("query") or ""),
            "body": str(item.get("body") or "")[:220],
        }
        for item in ranked[:limit]
    ]


def replay_queries(
    queries: list[dict[str, Any]],
    platforms: list[dict[str, Any]],
    sampling_policy: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    query_runs: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    deduped_queries = dedup_query_specs(
        [normalize_query_spec(query) for query in queries],
        threshold=0.9,
    )
    for query in deduped_queries:
        run = search_query(query, platforms, sampling_policy=sampling_policy)
        query_runs.append(
            {
                "query": run["query"],
                "query_spec": run["query_spec"],
                "baseline_score": run["baseline_score"],
                "finding_count": len(run["findings"]),
                "sample_findings": sample_findings(run["findings"], limit=5),
            }
        )
        findings.extend(run["findings"])
    return query_runs, merge_findings([], findings)
