# Self-written for task F201
from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

from autosearch.core.models import SubQuery


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "channels"
        / "devto"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_devto_api_search", module_path)
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
    return SubQuery(text="python", rationale="Need dev.to article coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_devto_articles_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["tag"] == "python"
        assert request.url.params["per_page"] == "10"
        return httpx.Response(
            200,
            json=[
                {
                    "title": "Practical Python pipelines",
                    "description": "A short guide to production-ready Python workflows.",
                    "url": "https://dev.to/alice/practical-python-pipelines",
                    "tag_list": ["python", "tutorial", "backend", "testing"],
                },
                {
                    "title": "Async retry patterns",
                    "description": "Notes from running retries in production.",
                    "url": "https://dev.to/bob/async-retry-patterns",
                    "tag_list": ["python", "asyncio"],
                },
            ],
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://dev.to/alice/practical-python-pipelines"
    assert first.title == "Practical Python pipelines"
    assert first.snippet == "A short guide to production-ready Python workflows."
    assert first.content == "A short guide to production-ready Python workflows."
    assert first.source_channel == "devto:python,tutorial,backend"

    second = results[1]
    assert second.url == "https://dev.to/bob/async-retry-patterns"
    assert second.title == "Async retry patterns"
    assert second.snippet == "Notes from running retries in production."
    assert second.content == "Notes from running retries in production."
    assert second.source_channel == "devto:python,asyncio"


@pytest.mark.asyncio
async def test_search_handles_article_without_tags() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "title": "Untagged article",
                    "description": "Still useful.",
                    "url": "https://dev.to/alice/untagged-article",
                    "tag_list": [],
                }
            ],
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].source_channel == "devto:"


@pytest.mark.asyncio
async def test_search_decodes_html_entities_in_title() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "title": "Python &amp; ML",
                    "description": "Entity decoding should happen in the title.",
                    "url": "https://dev.to/alice/python-ml",
                    "tag_list": ["python"],
                }
            ],
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "Python & ML"


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "devto_search_failed"
    assert "500" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_returns_empty_on_malformed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events == [
        (
            "devto_search_failed",
            {"reason": "invalid items payload"},
        )
    ]
