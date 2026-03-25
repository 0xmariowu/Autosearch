"""Cheap semantic-ish query dedup helpers."""

from __future__ import annotations

import math
import re
from typing import Any


STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "after", "before",
    "what", "when", "where", "which", "about", "have", "has", "will", "your", "using",
    "implementation", "guide",
}


def query_terms(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[A-Za-z0-9_\-]{3,}", str(text or "").lower())
        if token not in STOP_WORDS
    ]


def cosine_token_similarity(left: str, right: str) -> float:
    left_terms = query_terms(left)
    right_terms = query_terms(right)
    if not left_terms or not right_terms:
        return 0.0
    left_counts = {term: left_terms.count(term) for term in set(left_terms)}
    right_counts = {term: right_terms.count(term) for term in set(right_terms)}
    shared = set(left_counts) & set(right_counts)
    dot = sum(left_counts[term] * right_counts[term] for term in shared)
    left_norm = math.sqrt(sum(value * value for value in left_counts.values()))
    right_norm = math.sqrt(sum(value * value for value in right_counts.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if len(cleaned) < n:
        return [cleaned] if cleaned else []
    return [cleaned[index:index + n] for index in range(0, len(cleaned) - n + 1)]


def _cosine_from_terms(left_terms: list[str], right_terms: list[str]) -> float:
    if not left_terms or not right_terms:
        return 0.0
    left_counts = {term: left_terms.count(term) for term in set(left_terms)}
    right_counts = {term: right_terms.count(term) for term in set(right_terms)}
    shared = set(left_counts) & set(right_counts)
    dot = sum(left_counts[term] * right_counts[term] for term in shared)
    left_norm = math.sqrt(sum(value * value for value in left_counts.values()))
    right_norm = math.sqrt(sum(value * value for value in right_counts.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def semantic_query_similarity(left: str, right: str) -> float:
    token_cosine = cosine_token_similarity(left, right)
    char_cosine = _cosine_from_terms(_char_ngrams(left), _char_ngrams(right))
    left_terms = set(query_terms(left))
    right_terms = set(query_terms(right))
    overlap = len(left_terms & right_terms) / max(len(left_terms | right_terms), 1)
    return (0.5 * token_cosine) + (0.3 * char_cosine) + (0.2 * overlap)


def dedup_query_specs(
    queries: list[dict[str, Any]] | None,
    *,
    threshold: float = 0.9,
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    seen_texts: list[str] = []
    for query in list(queries or []):
        text = str((query or {}).get("text") or "").strip()
        if not text:
            continue
        duplicate = False
        for previous in seen_texts:
            if text == previous or semantic_query_similarity(text, previous) >= threshold:
                duplicate = True
                break
        if duplicate:
            continue
        kept.append(dict(query))
        seen_texts.append(text)
    return kept
