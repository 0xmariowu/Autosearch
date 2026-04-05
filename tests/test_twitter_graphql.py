"""Tests for Twitter GraphQL search and channel fallback behavior."""

from __future__ import annotations

import builtins
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MOCK_GRAPHQL_RESPONSE = {
    "data": {
        "search_by_raw_query": {
            "search_timeline": {
                "timeline": {
                    "instructions": [
                        {
                            "type": "TimelineAddEntries",
                            "entries": [
                                {
                                    "entryId": "tweet-123456",
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "rest_id": "123456",
                                                    "legacy": {
                                                        "full_text": "Test tweet about AI",
                                                        "favorite_count": 42,
                                                        "retweet_count": 10,
                                                        "reply_count": 5,
                                                        "quote_count": 2,
                                                        "created_at": "Wed Jan 15 14:30:00 +0000 2025",
                                                    },
                                                    "core": {
                                                        "user_results": {
                                                            "result": {
                                                                "legacy": {
                                                                    "screen_name": "testuser"
                                                                }
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        }
                                    },
                                }
                            ],
                        }
                    ]
                }
            }
        }
    }
}


def _make_async_client(
    *, response: MagicMock | None = None, side_effect: object | None = None
) -> AsyncMock:
    mock_client = AsyncMock()
    if side_effect is not None:
        mock_client.get = AsyncMock(side_effect=side_effect)
    else:
        mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _make_response(status_code: int, payload: dict | None = None) -> MagicMock:
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = payload or {}
    return mock_response


def test_get_credentials_from_env() -> None:
    graphql = importlib.import_module("channels.twitter.graphql")

    def getenv_side_effect(key: str, default: str = "") -> str:
        values = {
            "TWITTER_AUTH_TOKEN": "auth_token",
            "TWITTER_CT0": "ct0",
        }
        return values.get(key, default)

    with patch("channels.twitter.graphql.os.getenv", side_effect=getenv_side_effect):
        assert graphql.get_credentials() == ("auth_token", "ct0")


def test_get_credentials_returns_none_when_missing() -> None:
    graphql = importlib.import_module("channels.twitter.graphql")
    original_import = builtins.__import__

    def import_side_effect(
        name: str,
        globals: dict | None = None,
        locals: dict | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "browser_cookie3":
            raise ImportError("browser_cookie3 unavailable")
        return original_import(name, globals, locals, fromlist, level)

    with patch("channels.twitter.graphql.os.getenv", return_value=""), patch(
        "builtins.__import__", side_effect=import_side_effect
    ):
        assert graphql.get_credentials() is None


@pytest.mark.asyncio
async def test_search_graphql_parses_tweets() -> None:
    graphql = importlib.import_module("channels.twitter.graphql")

    mock_response = _make_response(200, MOCK_GRAPHQL_RESPONSE)
    mock_client = _make_async_client(response=mock_response)

    with patch(
        "channels.twitter.graphql.get_credentials",
        return_value=("auth_token", "ct0"),
    ), patch("channels.twitter.graphql.httpx.AsyncClient", return_value=mock_client):
        tweets = await graphql.search_graphql("AI", max_results=10)

    assert len(tweets) == 1
    tweet = tweets[0]
    assert tweet["url"] == "https://x.com/testuser/status/123456"
    assert tweet["text"] == "Test tweet about AI"
    assert tweet["author_handle"] == "testuser"
    assert tweet["likes"] == 42
    assert tweet["reposts"] == 10
    assert tweet["replies"] == 5


@pytest.mark.asyncio
async def test_search_graphql_returns_empty_on_error() -> None:
    graphql = importlib.import_module("channels.twitter.graphql")

    mock_client = _make_async_client(side_effect=Exception("connection refused"))

    with patch(
        "channels.twitter.graphql.get_credentials",
        return_value=("auth_token", "ct0"),
    ), patch("channels.twitter.graphql.httpx.AsyncClient", return_value=mock_client):
        tweets = await graphql.search_graphql("AI", max_results=10)

    assert tweets == []


@pytest.mark.asyncio
async def test_search_graphql_returns_empty_without_creds() -> None:
    graphql = importlib.import_module("channels.twitter.graphql")

    with patch("channels.twitter.graphql.get_credentials", return_value=None), patch(
        "channels.twitter.graphql.httpx.AsyncClient"
    ) as mock_async_client:
        tweets = await graphql.search_graphql("AI", max_results=10)

    assert tweets == []
    mock_async_client.assert_not_called()


@pytest.mark.asyncio
async def test_search_graphql_tries_fallback_on_404() -> None:
    graphql = importlib.import_module("channels.twitter.graphql")

    not_found_response = _make_response(404)
    success_response = _make_response(200, MOCK_GRAPHQL_RESPONSE)
    mock_client = _make_async_client(
        side_effect=[not_found_response, success_response]
    )

    with patch(
        "channels.twitter.graphql.get_credentials",
        return_value=("auth_token", "ct0"),
    ), patch("channels.twitter.graphql.httpx.AsyncClient", return_value=mock_client):
        tweets = await graphql.search_graphql("AI", max_results=10)

    assert len(tweets) == 1
    assert mock_client.get.await_count == 2
    first_url = mock_client.get.call_args_list[0].args[0]
    second_url = mock_client.get.call_args_list[1].args[0]
    assert graphql.DEFAULT_QUERY_ID in first_url
    assert graphql.FALLBACK_QUERY_IDS[0] in second_url


@pytest.mark.asyncio
async def test_search_falls_back_to_ddgs() -> None:
    twitter_search = importlib.import_module("channels.twitter.search")
    ddgs_results = [
        {
            "url": "https://x.com/testuser/status/123456",
            "title": "DDGS result",
            "snippet": "Fallback result",
        }
    ]

    with patch(
        "channels.twitter.search._search_graphql", new=AsyncMock(return_value=[])
    ) as mock_graphql, patch(
        "channels.twitter.search._search_ddgs",
        new=AsyncMock(return_value=ddgs_results),
    ) as mock_ddgs:
        results = await twitter_search.search("AI", max_results=5)

    assert results == ddgs_results
    mock_graphql.assert_awaited_once_with("AI", 5)
    mock_ddgs.assert_awaited_once_with("AI", 5)


@pytest.mark.asyncio
async def test_search_uses_graphql_when_available() -> None:
    twitter_search = importlib.import_module("channels.twitter.search")
    graphql_results = [
        {
            "url": "https://x.com/testuser/status/123456",
            "title": "GraphQL result",
            "snippet": "Primary result",
        }
    ]

    with patch(
        "channels.twitter.search._search_graphql",
        new=AsyncMock(return_value=graphql_results),
    ) as mock_graphql, patch(
        "channels.twitter.search._search_ddgs", new=AsyncMock(return_value=[])
    ) as mock_ddgs:
        results = await twitter_search.search("AI", max_results=5)

    assert results == graphql_results
    mock_graphql.assert_awaited_once_with("AI", 5)
    mock_ddgs.assert_not_awaited()
