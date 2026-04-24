# Self-written for task Plan-0420 W7 F701 + F702
from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

from autosearch.core.models import SubQuery


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "crossref"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_crossref_api_search", module_path)
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


def _query() -> SubQuery:
    return SubQuery(text="retrieval augmented generation", rationale="Need scholarly metadata")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _truncate_expected(text: str, *, max_length: int = 300) -> str:
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    if candidate and not candidate[-1].isspace():
        shortened = candidate.rsplit(None, 1)[0]
        if shortened:
            candidate = shortened

    return f"{candidate.rstrip()}…"


@pytest.mark.asyncio
async def test_search_maps_crossref_items_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query.title"] == "retrieval augmented generation"
        assert request.url.params["rows"] == "10"
        assert request.headers["accept"] == "application/json"
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": "10.1000/rag.2024.1",
                            "title": ["Retrieval-Augmented Generation Survey"],
                            "author": [
                                {"given": "Alice", "family": "Author"},
                                {"given": "Bob", "family": "Scientist"},
                            ],
                            "abstract": "<jats:p>RAG survey for large language models.</jats:p>",
                            "issued": {"date-parts": [[2024, 1, 1]]},
                            "container-title": ["Journal of AI Systems"],
                            "type": "journal-article",
                            "is-referenced-by-count": 123,
                            "URL": "https://doi.org/10.1000/rag.2024.1",
                        },
                        {
                            "DOI": "10.1000/rag.2023.2",
                            "title": ["Grounded Generation Benchmarks"],
                            "author": [
                                {"name": "Carol Researcher"},
                                {"given": "Dan", "family": "Writer"},
                                {"given": "Eve", "family": "Builder"},
                            ],
                            "published": {"date-parts": [[2023, 5, 20]]},
                            "container-title": ["Proceedings of ExampleConf"],
                            "type": "proceedings-article",
                            "is-referenced-by-count": 42,
                            "URL": "https://doi.org/10.1000/rag.2023.2",
                        },
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://doi.org/10.1000/rag.2024.1"
    assert first.title == "Retrieval-Augmented Generation Survey"
    assert first.snippet == "RAG survey for large language models."
    assert first.content == "RAG survey for large language models."
    assert first.source_channel == "crossref"

    second = results[1]
    assert second.url == "https://doi.org/10.1000/rag.2023.2"
    assert second.title == "Grounded Generation Benchmarks"
    assert (
        second.snippet == "Carol Researcher, Dan Writer, Eve Builder · Proceedings of ExampleConf"
        " · 2023 · proceedings-article · cited 42"
    )
    assert second.content == second.snippet


@pytest.mark.asyncio
async def test_search_skips_items_without_title_or_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": "10.1000/no-title",
                            "title": [],
                            "URL": "https://doi.org/10.1000/no-title",
                        },
                        {
                            "DOI": "",
                            "title": ["Missing URL"],
                            "URL": "",
                        },
                        {
                            "DOI": "10.1000/valid",
                            "title": ["Valid Paper"],
                            "URL": "https://doi.org/10.1000/valid",
                        },
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "Valid Paper"
    assert results[0].url == "https://doi.org/10.1000/valid"


@pytest.mark.asyncio
async def test_search_falls_back_to_doi_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": "10.5555/example",
                            "title": ["DOI Fallback"],
                            "URL": "",
                            "author": [{"name": "Fallback Author"}],
                            "issued": {"date-parts": [[2022]]},
                            "type": "journal-article",
                            "is-referenced-by-count": 7,
                        }
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://doi.org/10.5555/example"


@pytest.mark.asyncio
async def test_search_handles_empty_items() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"items": []}}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Bug 1 (fix-plan): typed exception now propagates instead of [].
    from autosearch.channels.base import (
        ChannelAuthError,
        PermanentError,
        RateLimited,
        TransientError,
    )

    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "bad gateway"}, request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events
    assert logger.events[0][0] == "crossref_search_failed"
    assert "502" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_truncates_long_abstract_and_keeps_full_content() -> None:
    long_abstract = "<jats:p>" + ("word " * 70) + "splitpoint continues after the limit</jats:p>"
    cleaned_abstract = ("word " * 70) + "splitpoint continues after the limit"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": "10.1000/long",
                            "title": ["Long Abstract Paper"],
                            "author": [{"name": "Long Author"}],
                            "abstract": long_abstract,
                            "issued": {"date-parts": [[2025]]},
                            "container-title": ["Journal of Long Abstracts"],
                            "type": "journal-article",
                            "is-referenced-by-count": 3,
                            "URL": "https://doi.org/10.1000/long",
                        }
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].snippet == _truncate_expected(cleaned_abstract)
    assert results[0].content == " ".join(cleaned_abstract.split())
    assert results[0].snippet is not None
    assert results[0].snippet.endswith("…")
