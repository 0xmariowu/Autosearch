"""Regression tests for consolidate_research context compression."""

from __future__ import annotations

from datetime import datetime

from autosearch.core.context_compression import compress_evidence


def test_compress_preserves_published_at_in_top_evidence() -> None:
    published_at = "2026-04-17T12:00:00+00:00"

    brief = compress_evidence(
        [
            {
                "url": "https://arxiv.org/abs/2401.12345",
                "title": "BM25 ranking explained",
                "snippet": "BM25 ranking uses term frequency and inverse document frequency.",
                "source": "arxiv",
                "published_at": published_at,
                "score": 0.7,
            }
        ],
        query="BM25 ranking",
    )

    assert brief["top_evidence"][0]["published_at"] == datetime.fromisoformat(published_at)


def test_compress_brief_uses_evidence_snippets_heading_not_findings() -> None:
    brief = compress_evidence(
        [
            {
                "url": "https://example.com/report",
                "title": "Weekly report",
                "snippet": "A raw excerpt from a source.",
                "source": "web",
            }
        ],
        query="weekly report",
    )

    assert "**Top evidence snippets:**" in brief["brief_text"]
    assert "findings" not in brief["brief_text"].lower()
