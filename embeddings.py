"""Semantic embedding helpers with optional model-backed backends.

The default path remains self-contained and deterministic, but this module now
supports upgrading to a real local embedding model when available. The runtime
chooses the strongest in-process backend it can load without introducing a hard
dependency on any external service.
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from functools import lru_cache
from typing import Protocol


Vector = dict[str, float] | list[float]


class EmbeddingBackend(Protocol):
    name: str

    def embed(self, text: str) -> Vector:
        ...


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_\-]{3,}", str(text or "").lower())


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if len(cleaned) < n:
        return [cleaned] if cleaned else []
    return [cleaned[index:index + n] for index in range(0, len(cleaned) - n + 1)]


def _sparse_embed(text: str) -> dict[str, float]:
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


class SparseEmbeddingBackend:
    name = "sparse-local"

    def embed(self, text: str) -> Vector:
        return _sparse_embed(text)


class SentenceTransformerEmbeddingBackend:
    def __init__(self, model_name: str) -> None:
        os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        from sentence_transformers import SentenceTransformer

        self.name = f"sentence-transformers:{model_name}"
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> Vector:
        vector = self._model.encode(
            str(text or ""),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [float(item) for item in vector.tolist()]


def _is_sparse(vector: Vector) -> bool:
    return isinstance(vector, dict)


def cosine_similarity(left: Vector, right: Vector) -> float:
    if not left or not right:
        return 0.0
    if _is_sparse(left) and _is_sparse(right):
        shared = set(left) & set(right)
        dot = sum(float(left[key]) * float(right[key]) for key in shared)
        left_norm = math.sqrt(sum(float(value) * float(value) for value in left.values()))
        right_norm = math.sqrt(sum(float(value) * float(value) for value in right.values()))
    else:
        left_values = list(left.values()) if _is_sparse(left) else list(left)
        right_values = list(right.values()) if _is_sparse(right) else list(right)
        width = min(len(left_values), len(right_values))
        if width <= 0:
            return 0.0
        dot = sum(float(left_values[index]) * float(right_values[index]) for index in range(width))
        left_norm = math.sqrt(sum(float(value) * float(value) for value in left_values))
        right_norm = math.sqrt(sum(float(value) * float(value) for value in right_values))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _embedding_backend_name() -> str:
    return str(os.environ.get("AUTOSEARCH_EMBEDDING_BACKEND") or "auto").strip().lower()


def _embedding_model_name() -> str:
    return str(
        os.environ.get("AUTOSEARCH_EMBEDDING_MODEL")
        or "sentence-transformers/all-MiniLM-L6-v2"
    ).strip()


@lru_cache(maxsize=4)
def _load_backend(name: str, model_name: str) -> EmbeddingBackend:
    normalized = str(name or "auto").strip().lower()
    if normalized == "sparse":
        return SparseEmbeddingBackend()
    if normalized in {"sentence_transformers", "sentence-transformers", "auto"}:
        try:
            return SentenceTransformerEmbeddingBackend(model_name)
        except Exception:
            if normalized != "auto":
                raise
    return SparseEmbeddingBackend()


def get_embedding_backend() -> EmbeddingBackend:
    return _load_backend(_embedding_backend_name(), _embedding_model_name())


def embed_text(text: str) -> Vector:
    return get_embedding_backend().embed(text)


def embedding_backend_name() -> str:
    return get_embedding_backend().name


def semantic_similarity(left_text: str, right_text: str) -> float:
    return cosine_similarity(embed_text(left_text), embed_text(right_text))
