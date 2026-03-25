"""Cheap lexical scoring and exact URL dedup."""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit, urlunsplit

from search_mesh.models import SearchHit


STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "after", "before",
    "what", "when", "where", "which", "about", "have", "has", "will", "your",
}


def normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def hit_domain(hit: SearchHit) -> str:
    parts = urlsplit(str(hit.url or "").strip())
    return str(parts.netloc or "").lower()


def _query_terms(query: str) -> list[str]:
    return [
        token for token in re.findall(r"[A-Za-z0-9_\-]{3,}", str(query or "").lower())
        if token not in STOP_WORDS
    ]


def lexical_score(query: str, hit: SearchHit, *, preferred_content_types: list[str] | None = None) -> int:
    terms = _query_terms(query)
    title = str(hit.title or "").lower()
    snippet = str(hit.snippet or "").lower()
    url = str(hit.url or "").lower()
    source = str(hit.source or "").lower()
    score = 0
    for term in terms:
        if term in title:
            score += 4
        if term in snippet:
            score += 2
        if term in url:
            score += 1
        if term in source:
            score += 1
    if preferred_content_types:
        lowered = {str(item or "").strip().lower() for item in list(preferred_content_types or []) if str(item or "").strip()}
        if hit.source.lower() in lowered or hit.backend.lower() in lowered:
            score += 2
    return score


def harmonic_position_bonus(rank: int) -> int:
    safe_rank = max(int(rank or 1), 1)
    return max(1, int(round(10 / safe_rank)))


def dedup_hits(hits: list[SearchHit], *, max_per_domain: int | None = None) -> list[SearchHit]:
    deduped: list[SearchHit] = []
    seen: set[str] = set()
    domain_counts: Counter[str] = Counter()
    for hit in list(hits or []):
        key = normalize_url(hit.url) or str(hit.title or "").strip().lower()
        if not key or key in seen:
            continue
        domain = hit_domain(hit)
        if max_per_domain is not None and domain and domain_counts[domain] >= int(max_per_domain):
            continue
        seen.add(key)
        if domain:
            domain_counts[domain] += 1
        deduped.append(hit)
    return deduped
