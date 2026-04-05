"""Tests for ScrapeCreators engine (Reddit + Twitter)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_response(status_code: int, json_data: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError

        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    resp.json.return_value = json_data
    return resp


def _mock_client(response: MagicMock) -> MagicMock:
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# --- Key missing returns [] ---


@pytest.mark.asyncio
async def test_search_reddit_no_key() -> None:
    from channels._engines.scrapecreators import search_reddit

    with patch("channels._engines.scrapecreators._get_api_key", return_value=""):
        result = await search_reddit("test", 5)
    assert result == []


@pytest.mark.asyncio
async def test_search_twitter_no_key() -> None:
    from channels._engines.scrapecreators import search_twitter

    with patch("channels._engines.scrapecreators._get_api_key", return_value=""):
        result = await search_twitter("test", 5)
    assert result == []


@pytest.mark.asyncio
async def test_fetch_comments_no_key() -> None:
    from channels._engines.scrapecreators import fetch_reddit_comments

    with patch("channels._engines.scrapecreators._get_api_key", return_value=""):
        result = await fetch_reddit_comments("https://reddit.com/r/test/1", 5)
    assert result == []


# --- Reddit search ---


@pytest.mark.asyncio
async def test_search_reddit_parses_posts() -> None:
    from channels._engines.scrapecreators import search_reddit

    api_response = {
        "data": [
            {
                "data": {
                    "permalink": "/r/test/comments/abc/hello/",
                    "title": "Hello World",
                    "selftext": "This is a test post",
                    "subreddit": "test",
                    "score": 42,
                    "num_comments": 10,
                    "created_utc": 1712000000,
                }
            }
        ]
    }

    mock = _mock_client(_mock_response(200, api_response))

    with (
        patch("channels._engines.scrapecreators._get_api_key", return_value="test-key"),
        patch("channels._engines.scrapecreators.httpx.AsyncClient", return_value=mock),
    ):
        results = await search_reddit("hello", 5)

    assert len(results) == 1
    assert results[0]["source"] == "reddit"
    assert "Hello World" in results[0]["title"]
    assert results[0]["metadata"]["score"] == 42


# --- Twitter search ---


@pytest.mark.asyncio
async def test_search_twitter_parses_tweets() -> None:
    from channels._engines.scrapecreators import search_twitter

    api_response = {
        "data": [
            {
                "id_str": "999",
                "text": "Test tweet about AI coding",
                "screen_name": "testuser",
                "favorite_count": 100,
                "retweet_count": 20,
                "reply_count": 5,
                "created_at": "2025-01-15T12:00:00Z",
            }
        ]
    }

    mock = _mock_client(_mock_response(200, api_response))

    with (
        patch("channels._engines.scrapecreators._get_api_key", return_value="test-key"),
        patch("channels._engines.scrapecreators.httpx.AsyncClient", return_value=mock),
    ):
        results = await search_twitter("AI coding", 5)

    assert len(results) == 1
    assert results[0]["source"] == "twitter"
    assert results[0]["metadata"]["likes"] == 100
    assert results[0]["metadata"]["author_handle"] == "testuser"


# --- Reddit comments ---


@pytest.mark.asyncio
async def test_fetch_comments_parses() -> None:
    from channels._engines.scrapecreators import fetch_reddit_comments

    api_response = {
        "data": [
            {
                "data": {
                    "author": "user1",
                    "body": "Great post, very helpful!",
                    "score": 50,
                }
            },
            {
                "data": {
                    "author": "[deleted]",
                    "body": "[deleted]",
                    "score": 10,
                }
            },
            {
                "data": {
                    "author": "user2",
                    "body": "I disagree with the premise",
                    "score": 20,
                }
            },
        ]
    }

    mock = _mock_client(_mock_response(200, api_response))

    with (
        patch("channels._engines.scrapecreators._get_api_key", return_value="test-key"),
        patch("channels._engines.scrapecreators.httpx.AsyncClient", return_value=mock),
    ):
        comments = await fetch_reddit_comments("https://reddit.com/r/test/1", 5)

    assert len(comments) == 2  # [deleted] filtered out
    assert comments[0]["score"] == 50  # sorted by score desc
    assert comments[0]["author"] == "user1"


# --- Error handling ---


@pytest.mark.asyncio
async def test_search_reddit_error_returns_empty() -> None:
    from channels._engines.scrapecreators import search_reddit

    mock = _mock_client(_mock_response(500, {}))

    with (
        patch("channels._engines.scrapecreators._get_api_key", return_value="test-key"),
        patch("channels._engines.scrapecreators.httpx.AsyncClient", return_value=mock),
    ):
        results = await search_reddit("test", 5)

    assert results == []


@pytest.mark.asyncio
async def test_search_twitter_error_returns_empty() -> None:
    from channels._engines.scrapecreators import search_twitter

    mock = _mock_client(_mock_response(401, {}))

    with (
        patch("channels._engines.scrapecreators._get_api_key", return_value="test-key"),
        patch("channels._engines.scrapecreators.httpx.AsyncClient", return_value=mock),
    ):
        results = await search_twitter("test", 5)

    assert results == []
