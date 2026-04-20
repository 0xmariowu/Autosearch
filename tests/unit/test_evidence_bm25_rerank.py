"""F506 module-level bench: EvidenceProcessor.rerank_bm25 sanity."""

from __future__ import annotations

from datetime import datetime, timezone

from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.models import Evidence


def _ev(url: str, content: str, title: str = "") -> Evidence:
    return Evidence(
        url=url,
        title=title or url,
        snippet=content[:200],
        content=content,
        source_channel="test",
        fetched_at=datetime.now(timezone.utc),
    )


def test_rerank_bm25_returns_most_relevant_first() -> None:
    processor = EvidenceProcessor()
    evs = [
        _ev("https://example.com/a", "cats are furry mammals that meow"),
        _ev(
            "https://example.com/b",
            "BM25 is a ranking function used by search engines to score documents",
        ),
        _ev("https://example.com/c", "blue whales are the largest mammals"),
    ]
    ranked = processor.rerank_bm25(evs, query="BM25 ranking function", top_k=3)
    assert len(ranked) == 3
    assert "example.com/b" in ranked[0].url
    # top_k is respected
    ranked2 = processor.rerank_bm25(evs, query="BM25", top_k=1)
    assert len(ranked2) == 1


def test_rerank_bm25_empty_query_returns_zero_scores() -> None:
    processor = EvidenceProcessor()
    evs = [_ev("https://example.com/a", "BM25 retrieval")]
    # Empty query → whitespace tokens empty → each evidence gets score=0.0 and
    # original order is preserved (top_k still caps).
    ranked = processor.rerank_bm25(evs, query="", top_k=5)
    assert len(ranked) == 1
    assert ranked[0].score == 0.0


def test_rerank_bm25_top_k_zero_returns_empty() -> None:
    processor = EvidenceProcessor()
    evs = [_ev("https://example.com/a", "anything")]
    assert processor.rerank_bm25(evs, query="anything", top_k=0) == []
