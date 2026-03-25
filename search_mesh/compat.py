"""Compatibility adapters for legacy search result shapes."""

from __future__ import annotations

from typing import Any

from search_mesh.models import SearchHitBatch


def batch_from_legacy_results(
    provider: str,
    query: str,
    results: list[Any] | None = None,
    *,
    backend: str = "",
    query_family: str = "unknown",
    error_alias: str = "",
) -> SearchHitBatch:
    items: list[dict[str, Any]] = []
    for result in list(results or []):
        items.append(
            {
                "title": str(getattr(result, "title", "") or ""),
                "url": str(getattr(result, "url", "") or ""),
                "body": str(getattr(result, "body", "") or ""),
                "source": str(getattr(result, "source", "") or provider),
                "eng": int(getattr(result, "eng", 0) or 0),
            }
        )
    return SearchHitBatch.from_hit_dicts(
        provider=str(provider or "").strip(),
        query=query,
        items=items,
        backend=backend or provider,
        query_family=query_family,
        error_alias=error_alias,
    )


def to_legacy_search_results(batch: SearchHitBatch) -> list[Any]:
    from engine import SearchResult

    return [
        SearchResult(
            title=hit.title,
            url=hit.url,
            eng=int(hit.score_hint or 0),
            body=hit.snippet,
            source=hit.source or hit.provider,
        )
        for hit in list(batch.hits or [])
    ]
