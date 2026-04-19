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
        / "stackoverflow"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_stackoverflow_api_search", module_path)
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
    return SubQuery(text="httpx retry middleware", rationale="Need Stack Overflow coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_stackoverflow_response_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "How to retry with httpx?",
                        "link": "https://stackoverflow.com/questions/123/example",
                        "tags": ["python", "async", "httpx", "retry"],
                        "body_markdown": "Use a transport wrapper around the client.",
                    },
                    {
                        "title": "Another question",
                        "link": "https://stackoverflow.com/questions/456/example",
                        "tags": ["pytest"],
                        "body_markdown": "Patch the client or inject a fake transport.",
                    },
                ],
                "quota_remaining": 299,
                "quota_max": 300,
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://stackoverflow.com/questions/123/example"
    assert first.title == "How to retry with httpx?"
    assert first.snippet == "Use a transport wrapper around the client."
    assert first.content == "Use a transport wrapper around the client."
    assert first.source_channel == "stackoverflow:python,async,httpx"

    second = results[1]
    assert second.url == "https://stackoverflow.com/questions/456/example"
    assert second.title == "Another question"
    assert second.snippet == "Patch the client or inject a fake transport."
    assert second.content == "Patch the client or inject a fake transport."
    assert second.source_channel == "stackoverflow:pytest"


@pytest.mark.asyncio
async def test_search_request_includes_filter_withbody() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["filter"] = request.url.params.get("filter", "")
        return httpx.Response(200, json={"items": []}, request=request)

    async with _client(handler) as http_client:
        await search(_query(), http_client=http_client)

    assert captured["filter"] == "withbody"


@pytest.mark.asyncio
async def test_search_handles_item_without_tags() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "No tags here",
                        "link": "https://stackoverflow.com/questions/789/example",
                        "tags": [],
                        "body_markdown": "Still a valid question body.",
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].source_channel == "stackoverflow"


@pytest.mark.asyncio
async def test_search_decodes_html_entities_in_title() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "How to use &quot;httpx&quot; retries?",
                        "link": "https://stackoverflow.com/questions/321/example",
                        "tags": ["python"],
                        "body_markdown": "Wrap the request execution in retry logic.",
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == 'How to use "httpx" retries?'


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "bad gateway"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "stackoverflow_search_failed"
    assert "502" in str(logger.events[0][1]["reason"])


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
            "stackoverflow_search_failed",
            {"reason": "invalid items payload"},
        )
    ]
