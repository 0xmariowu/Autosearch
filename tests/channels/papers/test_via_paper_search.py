from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from paper_search_mcp.paper import Paper

from autosearch.core.models import SubQuery


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "channels"
        / "papers"
        / "methods"
        / "via_paper_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_papers_via_paper_search", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
search = MODULE.search


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _paper(
    identifier: str,
    *,
    title: str | None = None,
    abstract: str = "Short abstract",
    url: str = "",
    pdf_url: str = "",
    source: str = "test-source",
) -> Paper:
    return Paper(
        paper_id=identifier,
        title=title or f"Paper {identifier}",
        authors=["Author One"],
        abstract=abstract,
        doi="10.1000/test",
        published_date=datetime(2026, 4, 19, tzinfo=UTC),
        pdf_url=pdf_url,
        url=url,
        source=source,
        updated_date=None,
        categories=[],
        keywords=[],
        citations=0,
        references=[],
        extra={},
    )


def _make_searcher(papers: list[Paper] | None = None, *, error: Exception | None = None) -> type:
    class _FakeSearcher:
        def search(self, query: str, max_results: int) -> list[Paper]:
            _ = (query, max_results)
            if error is not None:
                raise error
            return list(papers or [])

    return _FakeSearcher


def _query() -> SubQuery:
    return SubQuery(text="graph neural networks", rationale="Need paper coverage")


@pytest.mark.asyncio
async def test_search_aggregates_all_sources_into_evidence() -> None:
    sources = {
        "arxiv": _make_searcher(
            [
                _paper("a1", url="https://arxiv.org/abs/a1"),
                _paper("a2", url="https://arxiv.org/abs/a2"),
            ]
        ),
        "pubmed": _make_searcher(
            [
                _paper("p1", url="https://pubmed.ncbi.nlm.nih.gov/p1"),
                _paper("p2", url="https://pubmed.ncbi.nlm.nih.gov/p2"),
            ]
        ),
        "biorxiv": _make_searcher(
            [
                _paper("b1", url="https://www.biorxiv.org/content/b1"),
                _paper("b2", url="https://www.biorxiv.org/content/b2"),
            ]
        ),
        "medrxiv": _make_searcher(
            [
                _paper("m1", url="https://www.medrxiv.org/content/m1"),
                _paper("m2", url="https://www.medrxiv.org/content/m2"),
            ]
        ),
        "google_scholar": _make_searcher(
            [
                _paper("g1", url="https://scholar.google.com/g1"),
                _paper("g2", url="https://scholar.google.com/g2"),
            ]
        ),
    }

    results = await search(_query(), sources=sources)

    assert len(results) == 10
    assert [item.source_channel for item in results] == [
        "papers:arxiv",
        "papers:pubmed",
        "papers:biorxiv",
        "papers:medrxiv",
        "papers:google_scholar",
        "papers:arxiv",
        "papers:pubmed",
        "papers:biorxiv",
        "papers:medrxiv",
        "papers:google_scholar",
    ]


@pytest.mark.asyncio
async def test_search_filters_out_papers_without_url_or_pdf_url() -> None:
    sources = {
        "arxiv": _make_searcher(
            [
                _paper("missing", url="", pdf_url=""),
                _paper("valid", url="", pdf_url="https://arxiv.org/pdf/valid.pdf"),
            ]
        )
    }

    results = await search(_query(), sources=sources)

    assert len(results) == 1
    assert results[0].url == "https://arxiv.org/pdf/valid.pdf"


@pytest.mark.asyncio
async def test_search_dedupes_by_url() -> None:
    duplicate_url = "https://example.com/paper/shared"
    sources = {
        "arxiv": _make_searcher([_paper("a1", url=duplicate_url)]),
        "pubmed": _make_searcher([_paper("p1", url=duplicate_url)]),
    }

    results = await search(_query(), sources=sources)

    assert len(results) == 1
    assert results[0].url == duplicate_url
    assert results[0].source_channel == "papers:arxiv"


@pytest.mark.asyncio
async def test_search_snippet_truncates_at_300_chars_on_word_boundary() -> None:
    abstract = ("word " * 59) + "splitpoint continues after the limit"
    sources = {
        "arxiv": _make_searcher([_paper("a1", url="https://arxiv.org/abs/a1", abstract=abstract)])
    }

    results = await search(_query(), sources=sources)

    assert len(results) == 1
    assert results[0].snippet == f"{('word ' * 59).strip()}…"
    assert results[0].snippet is not None
    assert results[0].snippet.endswith("…")


@pytest.mark.asyncio
async def test_search_continues_when_one_source_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    sources = {
        "arxiv": _make_searcher([_paper("a1", url="https://arxiv.org/abs/a1")]),
        "pubmed": _make_searcher([_paper("p1", url="https://pubmed.ncbi.nlm.nih.gov/p1")]),
        "biorxiv": _make_searcher(error=RuntimeError("boom")),
        "medrxiv": _make_searcher([_paper("m1", url="https://www.medrxiv.org/content/m1")]),
        "google_scholar": _make_searcher([_paper("g1", url="https://scholar.google.com/g1")]),
    }

    results = await search(_query(), sources=sources)

    assert len(results) == 4
    assert logger.events == [
        (
            "papers_source_failed",
            {"source": "biorxiv", "reason": "boom"},
        )
    ]


@pytest.mark.asyncio
async def test_search_skips_source_that_exceeds_per_source_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    class _SlowSearcher:
        def search(self, query: str, max_results: int) -> list[Paper]:
            _ = (query, max_results)
            time.sleep(0.5)
            return []

    sources = {
        "arxiv": _make_searcher([_paper("a1", url="https://arxiv.org/abs/a1")]),
        "biorxiv": _SlowSearcher,
    }

    results = await search(_query(), sources=sources, per_source_timeout_seconds=0.05)

    assert len(results) == 1
    assert results[0].source_channel == "papers:arxiv"
    assert logger.events == [
        (
            "papers_source_timeout",
            {"source": "biorxiv", "timeout_seconds": 0.05},
        )
    ]


@pytest.mark.asyncio
async def test_search_tags_source_channel_with_source_name() -> None:
    sources = {
        "arxiv": _make_searcher([_paper("a1", url="https://arxiv.org/abs/a1")]),
        "pubmed": _make_searcher([_paper("p1", url="https://pubmed.ncbi.nlm.nih.gov/p1")]),
        "biorxiv": _make_searcher([_paper("b1", url="https://www.biorxiv.org/content/b1")]),
        "medrxiv": _make_searcher([_paper("m1", url="https://www.medrxiv.org/content/m1")]),
        "google_scholar": _make_searcher([_paper("g1", url="https://scholar.google.com/g1")]),
    }

    results = await search(_query(), sources=sources)

    assert [item.source_channel for item in results] == [
        "papers:arxiv",
        "papers:pubmed",
        "papers:biorxiv",
        "papers:medrxiv",
        "papers:google_scholar",
    ]
