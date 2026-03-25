"""Native search mesh hit contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from engine import PlatformSearchOutcome, SearchResult


def _hit_id(provider: str, title: str, url: str, query: str) -> str:
    raw = f"{provider}\n{title}\n{url}\n{query}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


@dataclass(frozen=True)
class SearchHit:
    hit_id: str
    url: str
    title: str
    snippet: str
    source: str
    provider: str
    query: str
    query_family: str = "unknown"
    backend: str = ""
    rank: int = 0
    score_hint: int = 0

    @classmethod
    def from_search_result(
        cls,
        result: SearchResult,
        *,
        provider: str,
        query: str,
        rank: int,
        backend: str = "",
        query_family: str = "unknown",
    ) -> "SearchHit":
        title = str(result.title or "").strip()
        url = str(result.url or "").strip()
        snippet = str(result.body or "")[:500]
        return cls(
            hit_id=_hit_id(provider, title, url, query),
            url=url,
            title=title,
            snippet=snippet,
            source=str(result.source or provider).strip(),
            provider=str(provider or "").strip(),
            query=str(query or "").strip(),
            query_family=str(query_family or "unknown").strip() or "unknown",
            backend=str(backend or provider).strip(),
            rank=int(rank),
            score_hint=int(result.eng or 0),
        )

    def to_search_result(self) -> SearchResult:
        return SearchResult(
            title=self.title,
            url=self.url,
            eng=int(self.score_hint or 0),
            body=self.snippet,
            source=self.source or self.provider,
        )


@dataclass
class SearchHitBatch:
    provider: str
    hits: list[SearchHit] = field(default_factory=list)
    error_alias: str = ""
    backend: str = ""

    @classmethod
    def from_platform_outcome(
        cls,
        outcome: PlatformSearchOutcome,
        *,
        query: str,
        backend: str = "",
        query_family: str = "unknown",
    ) -> "SearchHitBatch":
        provider = str(outcome.provider or "").strip()
        hits = [
            SearchHit.from_search_result(
                result,
                provider=provider,
                query=query,
                rank=index,
                backend=backend or provider,
                query_family=query_family,
            )
            for index, result in enumerate(list(outcome.results or []), start=1)
        ]
        return cls(
            provider=provider,
            hits=hits,
            error_alias=str(outcome.error_alias or "").strip(),
            backend=str(backend or provider).strip(),
        )

    def to_search_results(self) -> list[SearchResult]:
        return [hit.to_search_result() for hit in self.hits]

    def to_hit_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "hit_id": hit.hit_id,
                "url": hit.url,
                "title": hit.title,
                "snippet": hit.snippet,
                "source": hit.source,
                "provider": hit.provider,
                "query": hit.query,
                "query_family": hit.query_family,
                "backend": hit.backend,
                "rank": hit.rank,
                "score_hint": hit.score_hint,
            }
            for hit in self.hits
        ]
