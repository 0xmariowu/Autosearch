# Self-written for task F204
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
        / "podcast_cn"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_podcast_cn_api_search", module_path)
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
    return SubQuery(text="AI", rationale="Need Chinese podcast coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_itunes_results_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "resultCount": 2,
                "results": [
                    {
                        "collectionId": 1693183193,
                        "trackId": 1693183193,
                        "artistName": "FounderPark",
                        "collectionName": "AI局内人",
                        "collectionViewUrl": "https://podcasts.apple.com/cn/podcast/ai-show/id1",
                        "feedUrl": "https://example.com/feed-1.xml",
                        "trackCount": 42,
                        "primaryGenreName": "Technology",
                    },
                    {
                        "collectionId": 2693183193,
                        "trackId": 2693183193,
                        "artistName": "商业访谈",
                        "collectionName": "创业内幕",
                        "collectionViewUrl": "https://podcasts.apple.com/cn/podcast/business-show/id2",
                        "feedUrl": "https://example.com/feed-2.xml",
                        "trackCount": 18,
                        "primaryGenreName": "Business",
                    },
                ],
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://podcasts.apple.com/cn/podcast/ai-show/id1"
    assert first.title == "AI局内人 - FounderPark"
    assert first.snippet == "Technology podcast (Episodes: 42)"
    assert first.content == "Technology podcast (Episodes: 42)"
    assert first.source_channel == "podcast_cn:technology"

    second = results[1]
    assert second.url == "https://podcasts.apple.com/cn/podcast/business-show/id2"
    assert second.title == "创业内幕 - 商业访谈"
    assert second.source_channel == "podcast_cn:business"


@pytest.mark.asyncio
async def test_search_uses_feed_url_fallback_when_collection_view_url_missing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "resultCount": 1,
                "results": [
                    {
                        "artistName": "FounderPark",
                        "collectionName": "AI局内人",
                        "feedUrl": "https://example.com/feed-only.xml",
                        "trackCount": 42,
                        "primaryGenreName": "Technology",
                    }
                ],
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://example.com/feed-only.xml"


@pytest.mark.asyncio
async def test_search_skips_item_without_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "resultCount": 1,
                "results": [
                    {
                        "artistName": "FounderPark",
                        "collectionName": "AI局内人",
                        "trackCount": 42,
                        "primaryGenreName": "Technology",
                    }
                ],
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []


@pytest.mark.asyncio
async def test_search_sets_country_cn_param() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = request.url.query.decode()
        captured["country"] = request.url.params["country"]
        captured["media"] = request.url.params["media"]
        captured["entity"] = request.url.params["entity"]
        captured["limit"] = request.url.params["limit"]
        captured["term"] = request.url.params["term"]
        return httpx.Response(200, json={"resultCount": 0, "results": []}, request=request)

    async with _client(handler) as http_client:
        await search(_query(), http_client=http_client)

    assert "country=cn" in captured["query"]
    assert captured["country"] == "cn"
    assert captured["media"] == "podcast"
    assert captured["entity"] == "podcast"
    assert captured["limit"] == "10"
    assert captured["term"] == "AI"


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "podcast_cn_search_failed"
    assert "503" in str(logger.events[0][1]["reason"])
