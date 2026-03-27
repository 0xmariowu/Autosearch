"""Query helpers for local evidence index."""

from __future__ import annotations

from collections import Counter
from typing import Any


def _score(record: dict[str, Any], terms: list[str]) -> int:
    haystack = " ".join(
        [
            str(record.get("title") or ""),
            str(record.get("canonical_text") or ""),
            str(record.get("fit_markdown") or ""),
            str(record.get("source") or ""),
            str(record.get("domain") or ""),
        ]
    ).lower()
    counts = Counter(term for term in terms if term and term in haystack)
    return sum(counts.values())


def search_evidence(
    records: list[dict[str, Any]],
    query: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    terms = [term for term in str(query or "").lower().split() if len(term) >= 3]
    ranked = []
    for record in list(records or []):
        score = _score(record, terms)
        if score <= 0:
            continue
        ranked.append((score, record))
    ranked.sort(
        key=lambda item: (item[0], str(item[1].get("title") or "")), reverse=True
    )
    return [record for _, record in ranked[:limit]]
