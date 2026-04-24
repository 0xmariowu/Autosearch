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
        / "wikidata"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_wikidata_api_search", module_path)
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
    return SubQuery(text="python", rationale="Need entity definitions")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_wikidata_response_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["action"] == "wbsearchentities"
        assert request.url.params["search"] == "python"
        assert request.url.params["language"] == "en"
        assert request.url.params["limit"] == "10"
        assert request.url.params["type"] == "item"
        return httpx.Response(
            200,
            json={
                "search": [
                    {
                        "id": "Q2283",
                        "label": "Python",
                        "description": "general-purpose programming language",
                        "concepturi": "http://www.wikidata.org/entity/Q2283",
                    },
                    {
                        "id": "Q7477",
                        "label": "Monty Python",
                        "description": "British surreal comedy group",
                        "concepturi": "http://www.wikidata.org/entity/Q7477",
                    },
                ],
                "success": 1,
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "http://www.wikidata.org/entity/Q2283"
    assert first.title == "Python"
    assert first.snippet == "general-purpose programming language"
    assert first.content == "general-purpose programming language"
    assert first.source_channel == "wikidata:Q2283"

    second = results[1]
    assert second.url == "http://www.wikidata.org/entity/Q7477"
    assert second.title == "Monty Python"
    assert second.snippet == "British surreal comedy group"
    assert second.source_channel == "wikidata:Q7477"


@pytest.mark.asyncio
async def test_search_falls_back_to_q_id_url_when_concepturi_missing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "search": [
                    {
                        "id": "Q2283",
                        "label": "Python",
                        "description": "general-purpose programming language",
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://www.wikidata.org/wiki/Q2283"


@pytest.mark.asyncio
async def test_search_uses_label_as_title_fallback_to_id() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "search": [
                    {
                        "id": "Q2283",
                        "description": "general-purpose programming language",
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "Q2283"


@pytest.mark.asyncio
async def test_search_handles_entity_without_description() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "search": [
                    {
                        "id": "Q2283",
                        "label": "Python",
                        "concepturi": "http://www.wikidata.org/entity/Q2283",
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].snippet is None
    assert results[0].content is None


@pytest.mark.asyncio
async def test_search_sends_user_agent_with_contact_info() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        captured["accept"] = request.headers.get("accept", "")
        return httpx.Response(200, json={"search": []}, request=request)

    async with _client(handler) as http_client:
        await search(_query(), http_client=http_client)

    assert "autosearch/" in captured["user_agent"]
    assert "@" in captured["user_agent"] or "http" in captured["user_agent"]
    assert captured["accept"] == "application/json"


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
    assert logger.events[0][0] == "wikidata_search_failed"
    assert "500" in str(logger.events[0][1]["reason"])


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
        return httpx.Response(200, json={"success": 1}, request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events == [("wikidata_search_failed", {"reason": "invalid search payload"})]
