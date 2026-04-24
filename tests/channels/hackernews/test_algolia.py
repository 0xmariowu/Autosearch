"""G2-T6: Tests for hackernews channel algolia method."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_SKILL_DIR = Path(__file__).parents[3] / "autosearch/skills/channels/hackernews/methods"


def _load_search():
    import importlib.util

    spec = importlib.util.spec_from_file_location("hn_search", _SKILL_DIR / "algolia.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.search


@pytest.fixture()
def search():
    return _load_search()


@pytest.fixture()
def subquery():
    from autosearch.core.models import SubQuery

    return SubQuery(text="large language model", rationale="test")


_ALGOLIA_RESPONSE = {
    "hits": [
        {
            "objectID": "12345678",
            "title": "Ask HN: What's the best LLM for coding?",
            "url": "https://news.ycombinator.com/item?id=12345678",
            "author": "user1",
            "points": 250,
            "num_comments": 142,
        },
        {
            "objectID": "87654321",
            "title": "LLM evaluation benchmarks are broken",
            "url": "https://example.com/llm-eval",
            "author": "user2",
            "points": 180,
            "num_comments": 89,
        },
    ]
}


@pytest.mark.asyncio()
async def test_search_returns_evidence(search, subquery):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.json.return_value = _ALGOLIA_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search(subquery)

    assert len(results) >= 1
    assert results[0].source_channel == "hackernews"
    assert "ycombinator" in results[0].url or results[0].url.startswith("http")
    assert results[0].title


@pytest.mark.asyncio()
async def test_search_returns_empty_on_network_error(search, subquery):
    # Bug 1 (fix-plan): typed exception now propagates instead of [].
    from autosearch.channels.base import (
        ChannelAuthError,
        PermanentError,
        RateLimited,
        TransientError,
    )

    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("refused"),
    ):
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(subquery)
