from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.enrichment import enrich_reddit_items

MOCK_THREAD_JSON = [
    {
        "data": {
            "children": [
                {
                    "data": {
                        "upvote_ratio": 0.95,
                        "title": "Test Post",
                        "selftext": "Test content",
                        "score": 100,
                        "num_comments": 5,
                    }
                }
            ]
        }
    },
    {
        "data": {
            "children": [
                {
                    "kind": "t1",
                    "data": {
                        "author": "testuser",
                        "body": "This is a really great and detailed comment about the topic at hand which should be long enough for insights.",
                        "score": 50,
                        "created_utc": 1712000000,
                        "permalink": "/r/test/comments/abc/test_post/def",
                    },
                },
                {
                    "kind": "t1",
                    "data": {
                        "author": "[deleted]",
                        "body": "[deleted]",
                        "score": 30,
                        "created_utc": 1712000000,
                        "permalink": "/r/test/comments/abc/test_post/ghi",
                    },
                },
            ]
        }
    },
]


def _make_result(
    *,
    source: str = "reddit",
    url: str = "https://www.reddit.com/r/test/comments/abc/test_post/",
    composite_score: float = 0,
) -> dict:
    return {
        "url": url,
        "title": "Test result",
        "snippet": "Snippet",
        "source": source,
        "query": "test query",
        "metadata": {"composite_score": composite_score},
    }


def _make_response(
    *,
    status_code: int = 200,
    is_error: bool = False,
    json_data: object | None = None,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.is_error = is_error
    response.json = MagicMock(return_value=json_data)
    return response


def _setup_async_client(mock_async_client: MagicMock, get_impl: AsyncMock) -> MagicMock:
    mock_client = MagicMock()
    mock_client.get = get_impl
    mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_client


@pytest.mark.asyncio
async def test_enrich_adds_top_comments() -> None:
    result = _make_result()

    async def get(*args, **kwargs):
        return _make_response(json_data=MOCK_THREAD_JSON)

    with patch("lib.enrichment.httpx.AsyncClient") as mock_async_client:
        _setup_async_client(mock_async_client, AsyncMock(side_effect=get))
        await enrich_reddit_items([result], max_items=1)

    top_comments = result["metadata"]["top_comments"]
    assert isinstance(top_comments, list)
    assert len(top_comments) == 1
    assert top_comments[0] == {
        "score": 50,
        "author": "testuser",
        "excerpt": "This is a really great and detailed comment about the topic at hand which should be long enough for insights.",
        "date": datetime.fromtimestamp(1712000000, tz=timezone.utc).isoformat(),
    }


@pytest.mark.asyncio
async def test_enrich_adds_upvote_ratio() -> None:
    result = _make_result()

    async def get(*args, **kwargs):
        return _make_response(json_data=MOCK_THREAD_JSON)

    with patch("lib.enrichment.httpx.AsyncClient") as mock_async_client:
        _setup_async_client(mock_async_client, AsyncMock(side_effect=get))
        await enrich_reddit_items([result], max_items=1)

    assert result["metadata"]["upvote_ratio"] == 0.95


@pytest.mark.asyncio
async def test_enrich_skips_non_reddit() -> None:
    result = _make_result(source="hn", url="https://news.ycombinator.com/item?id=1")

    with patch("lib.enrichment.httpx.AsyncClient") as mock_async_client:
        await enrich_reddit_items([result], max_items=1)

    mock_async_client.assert_not_called()
    assert result["metadata"] == {"composite_score": 0}


@pytest.mark.asyncio
async def test_enrich_429_bails() -> None:
    first = _make_result(
        url="https://www.reddit.com/r/test/comments/abc/top_post/",
        composite_score=10,
    )
    second = _make_result(
        url="https://www.reddit.com/r/test/comments/def/second_post/",
        composite_score=5,
    )

    responses = [
        _make_response(status_code=429, is_error=True, json_data=None),
        _make_response(json_data=MOCK_THREAD_JSON),
    ]

    async def get(*args, **kwargs):
        return responses.pop(0)

    with patch("lib.enrichment.httpx.AsyncClient") as mock_async_client:
        _setup_async_client(mock_async_client, AsyncMock(side_effect=get))
        await enrich_reddit_items([first, second], max_items=2)

    assert "upvote_ratio" not in first["metadata"]
    assert "top_comments" not in first["metadata"]
    assert "upvote_ratio" not in second["metadata"]
    assert "top_comments" not in second["metadata"]


@pytest.mark.asyncio
async def test_enrich_filters_deleted_comments() -> None:
    result = _make_result()

    async def get(*args, **kwargs):
        return _make_response(json_data=MOCK_THREAD_JSON)

    with patch("lib.enrichment.httpx.AsyncClient") as mock_async_client:
        _setup_async_client(mock_async_client, AsyncMock(side_effect=get))
        await enrich_reddit_items([result], max_items=1)

    top_comments = result["metadata"]["top_comments"]
    assert len(top_comments) == 1
    assert [comment["author"] for comment in top_comments] == ["testuser"]


@pytest.mark.asyncio
async def test_enrich_comment_insights() -> None:
    result = _make_result()
    thread_json = deepcopy(MOCK_THREAD_JSON)
    thread_json[1]["data"]["children"].append(
        {
            "kind": "t1",
            "data": {
                "author": "anotheruser",
                "body": "One strong practical takeaway is that the implementation should keep the error handling simple and explicit for maintainability.",
                "score": 40,
                "created_utc": 1712000100,
                "permalink": "/r/test/comments/abc/test_post/jkl",
            },
        }
    )

    async def get(*args, **kwargs):
        return _make_response(json_data=thread_json)

    with patch("lib.enrichment.httpx.AsyncClient") as mock_async_client:
        _setup_async_client(mock_async_client, AsyncMock(side_effect=get))
        await enrich_reddit_items([result], max_items=1)

    insights = result["metadata"]["comment_insights"]
    assert 1 <= len(insights) <= 3
    assert all(isinstance(insight, str) and len(insight) > 30 for insight in insights)


@pytest.mark.asyncio
async def test_enrich_empty_results() -> None:
    await enrich_reddit_items([], max_items=3)


@pytest.mark.asyncio
async def test_enrich_network_error_silent() -> None:
    result = _make_result()
    original = deepcopy(result)

    with patch("lib.enrichment.httpx.AsyncClient") as mock_async_client:
        _setup_async_client(
            mock_async_client,
            AsyncMock(side_effect=RuntimeError("network down")),
        )
        await enrich_reddit_items([result], max_items=1)

    assert result == original
