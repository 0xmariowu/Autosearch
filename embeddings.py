"""Local semantic embedding helpers.

This module intentionally avoids hard runtime dependencies on external model
servers. It provides a lightweight in-process semantic vector space that can be
used for deduplication and chunk filtering.
"""

from __future__ import annotations

import math
import re
from collections import Counter


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_\-]{3,}", str(text or "").lower())


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if len(cleaned) < n:
        return [cleaned] if cleaned else []
    return [cleaned[index:index + n] for index in range(0, len(cleaned) - n + 1)]


def embed_text(text: str) -> dict[str, float]:
    """Return a lightweight sparse embedding map."""
    token_counts = Counter(_tokens(text))
    gram_counts = Counter(_char_ngrams(text))
    total_tokens = sum(token_counts.values()) or 1
    total_grams = sum(gram_counts.values()) or 1
    vector: dict[str, float] = {}
    for token, count in token_counts.items():
        vector[f"tok:{token}"] = count / total_tokens
    for gram, count in gram_counts.items():
        vector[f"chr:{gram}"] = (count / total_grams) * 0.5
    return vector


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    dot = sum(float(left[key]) * float(right[key]) for key in shared)
    left_norm = math.sqrt(sum(float(value) * float(value) for value in left.values()))
    right_norm = math.sqrt(sum(float(value) * float(value) for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def semantic_similarity(left_text: str, right_text: str) -> float:
    return cosine_similarity(embed_text(left_text), embed_text(right_text))
