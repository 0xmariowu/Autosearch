"""Regression test for simhash OverflowError path in EvidenceProcessor."""

from __future__ import annotations

from datetime import datetime, timezone

from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.models import Evidence


def _make_evidence(url: str, content: str) -> Evidence:
    return Evidence(
        url=url,
        title="Test",
        snippet=content[:200],
        content=content,
        source_channel="test",
        fetched_at=datetime.now(timezone.utc),
    )


def test_dedup_simhash_handles_overflow_without_crashing() -> None:
    """simhash 2.x raises OverflowError when a feature weight overflows uint8.

    Reproduction: a repetitive long text causes one feature to accumulate a
    weight > 255, and simhash's numpy path tries to store it in uint8. The
    dedup path must not let this crash the pipeline — evidence should still
    be kept, just without near-duplicate suppression for the offending item.
    """
    processor = EvidenceProcessor()

    pathological = "bm25 " * 600 + "retrieval ranking " * 400
    normal = "Short text about information retrieval."

    evs = [
        _make_evidence("https://example.com/1", pathological),
        _make_evidence("https://example.com/2", normal),
    ]

    kept = processor.dedup_simhash(evs)

    assert len(kept) == 2
    assert {e.url for e in kept} == {"https://example.com/1", "https://example.com/2"}


def test_dedup_simhash_deduplicates_identical_short_text() -> None:
    """Baseline — identical short text should still be deduped normally."""
    processor = EvidenceProcessor()
    text = "Same content about BM25 retrieval ranking algorithm."
    evs = [
        _make_evidence("https://example.com/a", text),
        _make_evidence("https://example.com/b", text),
    ]

    kept = processor.dedup_simhash(evs)

    assert len(kept) == 1
