"""Query-aware content filtering for acquired text."""

from __future__ import annotations

import re


def _terms(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9_\-]{4,}", str(query or "").lower())
    }


def _paragraph_score(paragraph: str, query_terms: set[str], index: int, total: int) -> tuple[int, int, int]:
    lowered = paragraph.lower()
    overlap = sum(1 for term in query_terms if term in lowered)
    density = len(re.findall(r"[A-Za-z0-9_\-]{4,}", paragraph))
    edge_bonus = 1 if index in {0, max(total - 1, 0)} else 0
    return (overlap, edge_bonus, density)


def select_relevant_content(text: str, *, query: str = "", max_chars: int = 2400) -> str:
    cleaned = str(text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    paragraphs = [item.strip() for item in cleaned.split("\n\n") if item.strip()]
    if len(paragraphs) <= 4:
        return cleaned[:max_chars].rsplit(" ", 1)[0].strip() or cleaned[:max_chars].strip()
    intro = paragraphs[:1]
    conclusion = paragraphs[-1:]
    middle = paragraphs[1:-1]
    terms = _terms(query)
    ranked_middle = sorted(
        enumerate(middle, start=1),
        key=lambda item: _paragraph_score(item[1], terms, item[0], len(paragraphs)),
        reverse=True,
    )
    selected_middle = [paragraph for _, paragraph in ranked_middle[:3]]
    selected = "\n\n".join(intro + selected_middle + conclusion)
    return selected[:max_chars].rsplit(" ", 1)[0].strip() or selected[:max_chars].strip()
