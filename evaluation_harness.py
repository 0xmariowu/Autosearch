"""Frozen bundle construction and anti-cheat metrics for goal loops."""

from __future__ import annotations

from collections import Counter, defaultdict
from urllib.parse import urlparse
from typing import Any

from evidence.legacy_adapter import normalize_legacy_finding


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _simpson_diversity(counts: Counter[str], total: int) -> float:
    if total <= 0 or not counts:
        return 0.0
    return round(1.0 - sum((count / total) ** 2 for count in counts.values()), 4)


def build_bundle(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    harness: dict[str, Any],
) -> list[dict[str, Any]]:
    policy = dict(harness.get("bundle_policy") or {})
    per_query_cap = int(policy.get("per_query_cap", 5) or 5)
    per_source_cap = int(policy.get("per_source_cap", 18) or 18)
    per_domain_cap = int(policy.get("per_domain_cap", 18) or 18)

    seen: set[str] = set()
    query_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    bundle: list[dict[str, Any]] = []
    for raw_item in list(existing) + list(incoming):
        item = normalize_legacy_finding(raw_item)
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        key = url or title
        if not key or key in seen:
            continue
        query = str(item.get("query") or "unknown")
        source = str(item.get("source") or "unknown")
        domain = _domain(url)
        if query_counts[query] >= per_query_cap:
            continue
        if source_counts[source] >= per_source_cap:
            continue
        if domain and domain_counts[domain] >= per_domain_cap:
            continue
        seen.add(key)
        query_counts[query] += 1
        source_counts[source] += 1
        if domain:
            domain_counts[domain] += 1
        bundle.append(item)
    return bundle


def bundle_metrics(
    bundle: list[dict[str, Any]],
    *,
    previous_bundle: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    previous_urls = {
        str(item.get("url") or "").strip()
        for item in list(previous_bundle or [])
        if str(item.get("url") or "").strip()
    }
    total = len(bundle)
    urls = [str(item.get("url") or "").strip() for item in bundle if str(item.get("url") or "").strip()]
    new_urls = [url for url in urls if url not in previous_urls]
    sources = [str(item.get("source") or "unknown") for item in bundle]
    queries = [str(item.get("query") or "unknown") for item in bundle]
    domains = [_domain(url) for url in urls if _domain(url)]

    source_counts = Counter(sources)
    query_counts = Counter(queries)
    domain_counts = Counter(domains)

    unique_sources = len(source_counts)
    unique_queries = len(query_counts)
    source_concentration = (max(source_counts.values()) / total) if total and source_counts else 1.0
    query_concentration = (max(query_counts.values()) / total) if total and query_counts else 1.0
    domain_concentration = (max(domain_counts.values()) / total) if total and domain_counts else 1.0

    title_prefixes = Counter()
    for item in bundle:
        title = str(item.get("title") or "").strip().lower()
        if not title:
            continue
        prefix = " ".join(title.split()[:3])
        if prefix:
            title_prefixes[prefix] += 1
    title_repetition = (max(title_prefixes.values()) / total) if total and title_prefixes else 0.0

    return {
        "total_findings": total,
        "unique_sources": unique_sources,
        "unique_queries": unique_queries,
        "source_diversity": _simpson_diversity(source_counts, total),
        "query_diversity": _simpson_diversity(query_counts, total),
        "source_concentration": round(source_concentration, 4),
        "query_concentration": round(query_concentration, 4),
        "domain_concentration": round(domain_concentration, 4),
        "title_repetition": round(title_repetition, 4),
        "new_unique_urls": len(set(new_urls)),
        "novelty_ratio": round((len(set(new_urls)) / total), 4) if total else 0.0,
        "new_sources": sorted({
            str(item.get("source") or "unknown")
            for item in bundle
            if str(item.get("url") or "").strip() in set(new_urls)
        }),
    }
