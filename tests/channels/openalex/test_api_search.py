# Self-written for task feat/huggingface-openalex-channels
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
        / "openalex"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_openalex_api_search", module_path)
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
    return SubQuery(text="retrieval augmented generation", rationale="Need paper coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _truncate_expected(text: str, *, max_length: int = 300) -> str:
    text = text.strip()
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    if candidate and not candidate[-1].isspace():
        shortened = candidate.rsplit(None, 1)[0]
        if shortened:
            candidate = shortened

    return f"{candidate.rstrip()}…"


def _inverted_index(text: str) -> dict[str, list[int]]:
    inverted: dict[str, list[int]] = {}
    for index, word in enumerate(text.split()):
        inverted.setdefault(word, []).append(index)
    return inverted


@pytest.mark.asyncio
async def test_search_maps_items_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "retrieval augmented generation"
        assert request.url.params["per-page"] == "10"
        assert request.headers["accept"] == "application/json"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "doi": "https://doi.org/10.48550/arxiv.2312.10997",
                        "title": "Retrieval-Augmented Generation for Large Language Models",
                        "publication_year": 2024,
                        "cited_by_count": 120,
                        "type": "preprint",
                        "abstract_inverted_index": _inverted_index(
                            "Retrieval augmented generation for large language models"
                        ),
                        "authorships": [
                            {"author": {"display_name": "Alice Researcher"}},
                            {"author": {"display_name": "Bob Scientist"}},
                        ],
                        "best_oa_location": {
                            "landing_page_url": "https://arxiv.org/abs/2312.10997"
                        },
                    },
                    {
                        "id": "https://openalex.org/W2",
                        "doi": "https://doi.org/10.1000/example",
                        "display_name": "Grounded Generation Benchmarks",
                        "publication_year": 2023,
                        "cited_by_count": 42,
                        "type": "article",
                        "abstract_inverted_index": _inverted_index(
                            "Grounded generation benchmarks"
                        ),
                        "authorships": [
                            {"author": {"display_name": "Carol Author"}},
                        ],
                    },
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://arxiv.org/abs/2312.10997"
    assert first.title == "Retrieval-Augmented Generation for Large Language Models"
    assert first.snippet == "Retrieval augmented generation for large language models"
    assert first.content == "Retrieval augmented generation for large language models"
    assert first.source_channel == "openalex"

    second = results[1]
    assert second.url == "https://doi.org/10.1000/example"
    assert second.title == "Grounded Generation Benchmarks"
    assert second.source_channel == "openalex"


@pytest.mark.asyncio
async def test_search_skips_items_without_required_fields() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "doi": "https://doi.org/10.1000/skip-me",
                        "publication_year": 2024,
                        "cited_by_count": 5,
                    },
                    {
                        "id": "https://openalex.org/W3",
                        "title": "Valid Paper",
                        "publication_year": 2024,
                        "cited_by_count": 6,
                        "type": "article",
                        "abstract_inverted_index": _inverted_index("Valid abstract"),
                    },
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "Valid Paper"


@pytest.mark.asyncio
async def test_search_handles_empty_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []}, request=request)

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
        return httpx.Response(500, json={"error": "boom"}, request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events
    assert logger.events[0][0] == "openalex_search_failed"
    assert "500" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_truncates_long_text_to_snippet() -> None:
    abstract = ("word " * 59) + "splitpoint continues after the limit"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W4",
                        "title": "Long Abstract Paper",
                        "publication_year": 2024,
                        "cited_by_count": 1,
                        "type": "article",
                        "abstract_inverted_index": _inverted_index(abstract),
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].snippet == _truncate_expected(abstract)
    assert results[0].content == abstract
    assert results[0].snippet is not None
    assert results[0].snippet.endswith("…")


@pytest.mark.asyncio
async def test_search_reconstructs_abstract_from_inverted_index() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W5",
                        "title": "Ordered Abstract",
                        "publication_year": 2024,
                        "cited_by_count": 9,
                        "type": "article",
                        "abstract_inverted_index": {
                            "generation": [2],
                            "Retrieval": [0],
                            "survey": [3],
                            "augmented": [1],
                        },
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].content == "Retrieval augmented generation survey"
    assert results[0].snippet == "Retrieval augmented generation survey"


@pytest.mark.asyncio
async def test_search_falls_back_to_doi_then_openalex_id_for_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W6",
                        "doi": "https://doi.org/10.1000/doi-only",
                        "title": "DOI Fallback",
                        "publication_year": 2024,
                        "cited_by_count": 3,
                        "type": "article",
                    },
                    {
                        "id": "https://openalex.org/W7",
                        "title": "OpenAlex Fallback",
                        "publication_year": 2023,
                        "cited_by_count": 1,
                        "type": "preprint",
                    },
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert [item.url for item in results] == [
        "https://doi.org/10.1000/doi-only",
        "https://openalex.org/W7",
    ]
