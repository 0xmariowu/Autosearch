"""Optional embedding-based snippet retrieval.

Requires `pip install "autosearch[embeddings]"`.

Usage:
    from autosearch.core.embeddings import (
        SentenceTransformerBackend,
        retrieve_for_section_by_embedding,
    )

Use this for paraphrase-heavy or cross-language section queries where BM25 may miss
semantic matches.
"""

from __future__ import annotations

import math
from typing import Protocol

import structlog

from autosearch.core.models import EvidenceSnippet

LOGGER = structlog.get_logger(__name__).bind(component="embeddings")
DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-MiniLM-L6-v2"


class EmbeddingsNotInstalledError(RuntimeError):
    """Raised when sentence-transformers is not installed."""


class EmbeddingBackend(Protocol):
    """Interface for embedding backends."""

    def encode_text(self, text: str) -> list[float]: ...
    def encode_batch(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...


class SentenceTransformerBackend:
    """sentence-transformers backend that lazy-loads its model on first use."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingsNotInstalledError(
                    "sentence-transformers not installed. "
                    'Install it with: pip install "autosearch[embeddings]"'
                ) from exc

            LOGGER.info("embedding_model_loading", model_name=self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode_text(self, text: str) -> list[float]:
        vector = self._load().encode(text, convert_to_numpy=True)
        return _to_list(vector)

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._load().encode(texts, convert_to_numpy=True)
        return [_to_list(vector) for vector in vectors]

    @property
    def dimension(self) -> int:
        dimension = self._load().get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError("Embedding model did not report a sentence embedding dimension.")
        return int(dimension)


def retrieve_for_section_by_embedding(
    section_query: str,
    snippets: list[EvidenceSnippet],
    *,
    backend: EmbeddingBackend,
    top_k: int = 15,
) -> list[EvidenceSnippet]:
    """Rank snippets by cosine similarity between the query and snippet embeddings.

    This is the embedding-based alternative to
    `autosearch.core.evidence.retrieve_for_section`. BM25 remains the default path.

    Empty snippets or empty query return `[]`.
    `top_k <= 0` returns every snippet ordered by descending score.
    """
    if not snippets or not section_query.strip():
        return []

    query_vector = backend.encode_text(section_query)
    snippet_vectors = backend.encode_batch([snippet.text for snippet in snippets])
    scores = _cosine_scores(query_vector, snippet_vectors)

    ranked = list(zip(snippets, scores, strict=True))
    ranked.sort(key=lambda item: float(item[1]), reverse=True)
    ordered = [snippet for snippet, _ in ranked]
    return ordered if top_k <= 0 else ordered[:top_k]


def _cosine_scores(query_vector: list[float], snippet_vectors: list[list[float]]) -> list[float]:
    try:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        LOGGER.debug("embedding_cosine_fallback_pure_python")
        return [_manual_cosine(query_vector, vector) for vector in snippet_vectors]

    query_array = np.array([query_vector], dtype=float)
    snippet_array = np.array(snippet_vectors, dtype=float)
    return [float(score) for score in cosine_similarity(query_array, snippet_array)[0]]


def _manual_cosine(left: list[float], right: list[float]) -> float:
    dot = sum(
        left_value * right_value for left_value, right_value in zip(left, right, strict=False)
    )
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _to_list(vector: object) -> list[float]:
    if hasattr(vector, "tolist"):
        values = vector.tolist()
    else:
        values = vector
    return [float(value) for value in values]


__all__ = [
    "DEFAULT_MODEL_NAME",
    "EmbeddingBackend",
    "EmbeddingsNotInstalledError",
    "SentenceTransformerBackend",
    "retrieve_for_section_by_embedding",
]
