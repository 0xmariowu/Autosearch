"""Tests for autosearch.core.citation_index."""

from __future__ import annotations

import pytest

from autosearch.core import citation_index as ci


@pytest.fixture(autouse=True)
def _clear_indexes():
    ci._CITATION_INDEXES.clear()
    yield
    ci._CITATION_INDEXES.clear()


def test_create_returns_valid_index_id():
    index_id = ci.create_index()
    assert isinstance(index_id, str) and len(index_id) > 0
    assert index_id in ci._CITATION_INDEXES


def test_add_same_url_twice_returns_same_number():
    index_id = ci.create_index()
    num1 = ci.add_citation(index_id, "https://example.com", title="Ex")
    num2 = ci.add_citation(index_id, "https://example.com", title="Ex again")
    assert num1 == num2


def test_add_different_urls_returns_different_numbers():
    index_id = ci.create_index()
    num1 = ci.add_citation(index_id, "https://example.com/a")
    num2 = ci.add_citation(index_id, "https://example.com/b")
    assert num1 != num2
    assert num2 == num1 + 1


def test_export_produces_markdown_with_citation_numbers():
    index_id = ci.create_index()
    ci.add_citation(index_id, "https://example.com/a", title="Article A", source="Blog")
    ci.add_citation(index_id, "https://example.com/b", title="Article B")
    markdown = ci.export_citations(index_id)
    assert "[1]" in markdown and "[2]" in markdown
    assert "https://example.com/a" in markdown
    assert "https://example.com/b" in markdown


def test_merge_combines_and_deduplicates():
    target_id = ci.create_index()
    source_id = ci.create_index()
    ci.add_citation(target_id, "https://example.com/shared")
    ci.add_citation(source_id, "https://example.com/shared")
    ci.add_citation(source_id, "https://example.com/new", title="New")
    result = ci.merge_index(target_id, source_id)
    assert result["merged_count"] == 1
    assert result["skipped_duplicates"] == 1
    urls = [e["url"] for e in ci._CITATION_INDEXES[target_id]._entries]
    assert "https://example.com/new" in urls
