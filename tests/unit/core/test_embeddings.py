# Self-written, plan v2.3 § 13.5 W6 scaffold
import builtins
from datetime import datetime

import pytest

from autosearch.core.embeddings import (
    EmbeddingsNotInstalledError,
    SentenceTransformerBackend,
    retrieve_for_section_by_embedding,
)
from autosearch.core.models import EvidenceSnippet

NOW = datetime(2026, 4, 20, 12, 0, 0)


class FakeBackend:
    def __init__(self, vectors_by_text: dict[str, list[float]]) -> None:
        self.vectors_by_text = vectors_by_text

    def encode_text(self, text: str) -> list[float]:
        return self.vectors_by_text.get(text, [0.0, 0.0, 0.0])

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.encode_text(text) for text in texts]

    @property
    def dimension(self) -> int:
        return 3


class FakeVector:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return list(self.values)


def make_snippet(evidence_id: str, text: str, offset: int = 0) -> EvidenceSnippet:
    return EvidenceSnippet(
        evidence_id=evidence_id,
        text=text,
        offset=offset,
        source_url=f"https://example.com/{evidence_id}",
        source_title=f"Source {evidence_id}",
    )


def test_retrieve_empty_snippets_returns_empty() -> None:
    backend = FakeBackend({"query": [1.0, 0.0, 0.0]})

    assert retrieve_for_section_by_embedding("query", [], backend=backend) == []


def test_retrieve_empty_query_returns_empty() -> None:
    backend = FakeBackend({})
    snippets = [make_snippet("one", "snippet one")]

    assert retrieve_for_section_by_embedding("   ", snippets, backend=backend) == []


def test_retrieve_ranks_by_cosine_similarity() -> None:
    backend = FakeBackend(
        {
            "query": [1.0, 0.0, 0.0],
            "snippet-1": [0.2, 0.98, 0.0],
            "snippet-2": [0.95, 0.1, 0.0],
            "snippet-3": [-1.0, 0.0, 0.0],
        }
    )
    snippets = [
        make_snippet("one", "snippet-1"),
        make_snippet("two", "snippet-2"),
        make_snippet("three", "snippet-3"),
    ]

    ranked = retrieve_for_section_by_embedding("query", snippets, backend=backend, top_k=3)

    assert [snippet.evidence_id for snippet in ranked] == ["two", "one", "three"]


def test_retrieve_top_k_caps_results() -> None:
    backend = FakeBackend(
        {
            "query": [1.0, 0.0, 0.0],
            "a": [1.0, 0.0, 0.0],
            "b": [0.8, 0.2, 0.0],
            "c": [0.1, 0.9, 0.0],
        }
    )
    snippets = [
        make_snippet("a", "a"),
        make_snippet("b", "b"),
        make_snippet("c", "c"),
    ]

    ranked = retrieve_for_section_by_embedding("query", snippets, backend=backend, top_k=2)

    assert [snippet.evidence_id for snippet in ranked] == ["a", "b"]


def test_retrieve_top_k_zero_returns_all_sorted() -> None:
    backend = FakeBackend(
        {
            "query": [1.0, 0.0, 0.0],
            "a": [0.3, 0.95, 0.0],
            "b": [1.0, 0.0, 0.0],
            "c": [-1.0, 0.0, 0.0],
        }
    )
    snippets = [
        make_snippet("a", "a"),
        make_snippet("b", "b"),
        make_snippet("c", "c"),
    ]

    ranked = retrieve_for_section_by_embedding("query", snippets, backend=backend, top_k=0)

    assert [snippet.evidence_id for snippet in ranked] == ["b", "a", "c"]


def test_retrieve_handles_zero_vector_without_crash() -> None:
    backend = FakeBackend(
        {
            "query": [0.0, 0.0, 0.0],
            "a": [1.0, 0.0, 0.0],
            "b": [0.0, 1.0, 0.0],
        }
    )
    snippets = [
        make_snippet("a", "a"),
        make_snippet("b", "b"),
    ]

    ranked = retrieve_for_section_by_embedding("query", snippets, backend=backend, top_k=0)

    assert ranked == snippets


def test_sentence_transformer_backend_raises_when_not_installed(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "sentence_transformers":
            raise ImportError("No module named 'sentence_transformers'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    backend = SentenceTransformerBackend()

    with pytest.raises(
        EmbeddingsNotInstalledError,
        match=r'pip install "autosearch\[embeddings\]"',
    ):
        backend.encode_text("query")


def test_sentence_transformer_backend_does_not_load_until_used(monkeypatch) -> None:
    backend = SentenceTransformerBackend()

    assert backend._model is None

    class FakeModel:
        def encode(self, text: str, *, convert_to_numpy: bool) -> FakeVector:
            assert text == "query"
            assert convert_to_numpy is True
            return FakeVector([1.0, 0.0, 0.0])

    def fake_load() -> FakeModel:
        backend._model = FakeModel()
        return backend._model

    monkeypatch.setattr(backend, "_load", fake_load)

    assert backend.encode_text("query") == [1.0, 0.0, 0.0]
    assert backend._model is not None
