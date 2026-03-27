"""Native search mesh hit contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


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
    def from_fields(
        cls,
        *,
        url: str,
        title: str,
        snippet: str,
        source: str,
        provider: str,
        query: str,
        rank: int,
        backend: str = "",
        query_family: str = "unknown",
        score_hint: int = 0,
    ) -> "SearchHit":
        clean_title = str(title or "").strip()
        clean_url = str(url or "").strip()
        clean_snippet = str(snippet or "")[:500]
        clean_provider = str(provider or "").strip()
        return cls(
            hit_id=_hit_id(clean_provider, clean_title, clean_url, query),
            url=clean_url,
            title=clean_title,
            snippet=clean_snippet,
            source=str(source or clean_provider).strip(),
            provider=clean_provider,
            query=str(query or "").strip(),
            query_family=str(query_family or "unknown").strip() or "unknown",
            backend=str(backend or clean_provider).strip(),
            rank=int(rank),
            score_hint=int(score_hint or 0),
        )

    @classmethod
    def from_mapping(
        cls,
        payload: dict[str, Any],
        *,
        provider: str,
        query: str,
        rank: int,
        backend: str = "",
        query_family: str = "unknown",
    ) -> "SearchHit":
        return cls.from_fields(
            url=str(payload.get("url") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            snippet=str(payload.get("snippet") or payload.get("body") or "").strip(),
            source=str(payload.get("source") or provider).strip(),
            provider=provider,
            query=query,
            rank=rank,
            backend=backend,
            query_family=query_family,
            score_hint=int(payload.get("score_hint", payload.get("eng", 0)) or 0),
        )


@dataclass
class SearchHitBatch:
    provider: str
    hits: list[SearchHit] = field(default_factory=list)
    error_alias: str = ""
    backend: str = ""

    @classmethod
    def from_hit_dicts(
        cls,
        *,
        provider: str,
        query: str,
        items: list[dict[str, Any]] | None = None,
        backend: str = "",
        query_family: str = "unknown",
        error_alias: str = "",
    ) -> "SearchHitBatch":
        hits = [
            SearchHit.from_mapping(
                item,
                provider=provider,
                query=query,
                rank=index,
                backend=backend or provider,
                query_family=query_family,
            )
            for index, item in enumerate(list(items or []), start=1)
        ]
        return cls(
            provider=str(provider or "").strip(),
            hits=hits,
            error_alias=str(error_alias or "").strip(),
            backend=str(backend or provider).strip(),
        )

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
