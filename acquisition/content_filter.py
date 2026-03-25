"""Query-aware content filtering for acquired text."""

from __future__ import annotations

import math
import re

from embeddings import semantic_similarity as embedding_semantic_similarity


def _terms(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9_\-]{4,}", str(query or "").lower())
    }


def _split_chunks(paragraph: str) -> list[str]:
    stripped = str(paragraph or "").strip()
    if not stripped:
        return []
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", stripped) if item.strip()]
    if len(sentences) <= 3:
        return [stripped]
    chunks: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        current.append(sentence)
        if len(current) >= 3:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks or [stripped]


def _bm25ish_score(text: str, query_terms: set[str]) -> float:
    tokens = re.findall(r"[A-Za-z0-9_\-]{4,}", str(text or "").lower())
    if not tokens or not query_terms:
        return 0.0
    token_count = len(tokens)
    unique = set(tokens)
    score = 0.0
    for term in query_terms:
        tf = tokens.count(term)
        if not tf:
            continue
        rarity = math.log((1 + token_count) / (1 + sum(1 for token in unique if token == term))) + 1.0
        score += (tf / (tf + 1.2)) * rarity
    coverage = len(query_terms & unique) / max(len(query_terms), 1)
    return score + coverage


def _embedding_score(text: str, query: str) -> float:
    if not str(query or "").strip():
        return 0.0
    return embedding_semantic_similarity(text, query)


def _paragraph_score(paragraph: str, query_terms: set[str], query: str, index: int, total: int) -> tuple[float, int, int]:
    lowered = paragraph.lower()
    overlap = sum(1 for term in query_terms if term in lowered)
    bm25ish = _bm25ish_score(paragraph, query_terms)
    semantic = _embedding_score(paragraph, query)
    density = len(re.findall(r"[A-Za-z0-9_\-]{4,}", paragraph))
    edge_bonus = 1 if index in {0, max(total - 1, 0)} else 0
    return (bm25ish + overlap + semantic, edge_bonus, density)


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
    expanded_middle: list[tuple[int, str]] = []
    for index, paragraph in enumerate(middle, start=1):
        for chunk in _split_chunks(paragraph):
            expanded_middle.append((index, chunk))
    ranked_middle = sorted(
        expanded_middle,
        key=lambda item: _paragraph_score(item[1], terms, query, item[0], len(paragraphs)),
        reverse=True,
    )
    selected_middle = [paragraph for _, paragraph in ranked_middle[:3]]
    selected = "\n\n".join(intro + selected_middle + conclusion)
    return selected[:max_chars].rsplit(" ", 1)[0].strip() or selected[:max_chars].strip()
