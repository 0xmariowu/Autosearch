# Self-written for task F202
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
        / "wikipedia"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_wikipedia_api_search", module_path)
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
    return SubQuery(text="large language model", rationale="Need encyclopedia coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_wikipedia_response_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["action"] == "query"
        assert request.url.params["list"] == "search"
        assert request.url.params["srsearch"] == "large language model"
        assert request.url.params["srlimit"] == "10"
        assert request.url.params["srprop"] == "snippet"
        return httpx.Response(
            200,
            json={
                "query": {
                    "search": [
                        {
                            "title": "Large language model &amp; AI",
                            "snippet": (
                                'A <span class="searchmatch">large language</span> model'
                                " &amp; system."
                            ),
                            "pageid": 12345,
                        },
                        {
                            "title": "Python &quot;language&quot;",
                            "snippet": "Programming language article.",
                            "pageid": 67890,
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
    assert first.url == "https://en.wikipedia.org/?curid=12345"
    assert first.title == "Large language model & AI"
    assert first.snippet == "A large language model & system."
    assert first.content == "A large language model & system."
    assert first.source_channel == "wikipedia:en"

    second = results[1]
    assert second.url == "https://en.wikipedia.org/?curid=67890"
    assert second.title == 'Python "language"'
    assert second.snippet == "Programming language article."
    assert second.source_channel == "wikipedia:en"


@pytest.mark.asyncio
async def test_search_strips_span_markers_from_snippet() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "search": [
                        {
                            "title": "Example",
                            "snippet": '<span class="searchmatch">foo</span> bar',
                            "pageid": 123,
                        }
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].snippet == "foo bar"


@pytest.mark.asyncio
async def test_search_decodes_html_entities() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "search": [
                        {
                            "title": "Python (programming language)",
                            "snippet": "&quot;Python&quot; is a programming language.",
                            "pageid": 23862,
                        }
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "Python (programming language)"
    assert results[0].snippet == '"Python" is a programming language.'


@pytest.mark.asyncio
async def test_search_skips_item_without_pageid() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "search": [
                        {
                            "title": "Missing pageid",
                            "snippet": "Should be skipped.",
                        }
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []


@pytest.mark.asyncio
async def test_search_sends_user_agent_with_contact_info() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        captured["accept"] = request.headers.get("accept", "")
        return httpx.Response(200, json={"query": {"search": []}}, request=request)

    async with _client(handler) as http_client:
        await search(_query(), http_client=http_client)

    assert "autosearch/" in captured["user_agent"]
    assert "@" in captured["user_agent"] or "http" in captured["user_agent"]
    assert captured["accept"] == "application/json"


@pytest.mark.asyncio
async def test_search_returns_empty_on_malformed_payload(
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
        return httpx.Response(200, json={"query": {}}, request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events == [("wikipedia_search_failed", {"reason": "invalid search payload"})]


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
    assert logger.events[0][0] == "wikipedia_search_failed"
    assert "500" in str(logger.events[0][1]["reason"])
