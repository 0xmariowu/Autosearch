"""Tests for searxng channel."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_SKILL_DIR = Path(__file__).parents[3] / "autosearch/skills/channels/searxng/methods"


def _load_search():
    import importlib.util

    spec = importlib.util.spec_from_file_location("searxng_search", _SKILL_DIR / "api_search.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.search


@pytest.fixture()
def search():
    return _load_search()


@pytest.fixture()
def subquery():
    from autosearch.core.models import SubQuery

    return SubQuery(text="e2b sandbox python", rationale="test")


_SEARXNG_RESPONSE = {
    "results": [
        {
            "title": "E2B — Code Interpreter SDK",
            "url": "https://e2b.dev",
            "content": "Run AI-generated code safely",
            "engine": "google",
        },
        {
            "title": "E2B GitHub",
            "url": "https://github.com/e2b-dev/e2b",
            "content": "Open source sandbox",
            "engine": "bing",
        },
    ]
}


@pytest.mark.asyncio()
async def test_search_returns_evidence_when_url_set(search, subquery):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.json.return_value = _SEARXNG_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with (
        patch.dict("os.environ", {"SEARXNG_URL": "http://localhost:8080"}),
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp),
    ):
        results = await search(subquery)

    assert len(results) == 2
    assert results[0].source_channel == "searxng"
    assert results[0].url == "https://e2b.dev"
    assert "[google]" in (results[0].snippet or "")


@pytest.mark.asyncio()
async def test_search_raises_unavailable_when_no_url(search, subquery):
    from autosearch.channels.base import MethodUnavailable

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(MethodUnavailable, match="SEARXNG_URL"):
            await search(subquery)


@pytest.mark.asyncio()
async def test_search_returns_empty_on_http_error(search, subquery):
    # Bug 1 (fix-plan): typed exception now propagates instead of [].
    from autosearch.channels.base import (
        ChannelAuthError,
        PermanentError,
        RateLimited,
        TransientError,
    )

    with (
        patch.dict("os.environ", {"SEARXNG_URL": "http://localhost:8080"}),
        patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ),
    ):
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(subquery)
