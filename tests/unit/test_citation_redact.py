"""Tests for citation export URL redaction."""

from __future__ import annotations

from autosearch.core.citation_index import add_citation, create_index, export_citations


def test_export_citations_default_redacts_signed_urls() -> None:
    index_id = create_index()
    add_citation(
        index_id,
        "https://bucket.s3.amazonaws.com/key.txt?X-Amz-Signature=abc&keepme=ok",
    )

    output = export_citations(index_id)

    assert "X-Amz-Signature" not in output


def test_export_citations_raw_urls_keeps_signed() -> None:
    index_id = create_index()
    add_citation(
        index_id,
        "https://bucket.s3.amazonaws.com/key.txt?X-Amz-Signature=abc&keepme=ok",
    )

    output = export_citations(index_id, raw_urls=True)

    assert "X-Amz-Signature" in output
