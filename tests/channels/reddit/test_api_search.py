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
        / "autosearch"
        / "skills"
        / "channels"
        / "reddit"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_reddit_api_search", module_path)
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
    return SubQuery(text="httpx retries", rationale="Need Reddit discussion coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_reddit_response_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "httpx retries"
        assert request.url.params["limit"] == "10"
        assert request.url.params["raw_json"] == "1"
        return httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {
                            "kind": "t3",
                            "data": {
                                "title": "Self post title",
                                "selftext": "This is a text post with details.",
                                "url": "https://example.com/ignored",
                                "permalink": "/r/python/comments/abc123/self_post_title/",
                                "subreddit": "python",
                                "is_self": True,
                            },
                        },
                        {
                            "kind": "t3",
                            "data": {
                                "title": "Link post title",
                                "selftext": "",
                                "url": "https://example.com/post",
                                "permalink": "/r/programming/comments/def456/link_post_title/",
                                "subreddit": "programming",
                                "is_self": False,
                            },
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
    assert first.url == "https://www.reddit.com/r/python/comments/abc123/self_post_title/"
    assert first.title == "Self post title"
    assert first.snippet == "This is a text post with details."
    assert first.content == "This is a text post with details."
    assert first.source_channel == "reddit:r/python"

    second = results[1]
    assert second.url == "https://example.com/post"
    assert second.title == "Link post title"
    assert second.snippet is None
    assert second.content is None
    assert second.source_channel == "reddit:r/programming"


@pytest.mark.asyncio
async def test_search_skips_entries_without_resolvable_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {
                            "kind": "t3",
                            "data": {
                                "title": "Broken self post",
                                "selftext": "No permalink here.",
                                "url": "",
                                "permalink": "",
                                "subreddit": "python",
                                "is_self": True,
                            },
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
async def test_search_sets_user_agent_header() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json={"data": {"children": []}}, request=request)

    async with _client(handler) as http_client:
        await search(_query(), http_client=http_client)

    assert "autosearch/" in captured["user_agent"]
    assert captured["user_agent"] != ""


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
        return httpx.Response(429, json={"message": "slow down"}, request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events
    assert logger.events[0][0] == "reddit_search_failed"
    assert "429" in str(logger.events[0][1]["reason"])


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
        return httpx.Response(200, json={"data": {}}, request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events == [
        (
            "reddit_search_failed",
            {"reason": "invalid children payload"},
        )
    ]


@pytest.mark.asyncio
async def test_search_truncates_snippet_on_word_boundary() -> None:
    long_selftext = ("word " * 59) + "splitpoint continues after the limit"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {
                            "kind": "t3",
                            "data": {
                                "title": "Long post",
                                "selftext": long_selftext,
                                "url": "https://example.com/ignored",
                                "permalink": "/r/python/comments/ghi789/long_post/",
                                "subreddit": "python",
                                "is_self": True,
                            },
                        }
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].snippet == f"{('word ' * 59).strip()}…"
    assert results[0].snippet is not None
    assert results[0].snippet.endswith("…")
