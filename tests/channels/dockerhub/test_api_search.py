"""Tests for dockerhub channel."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_SKILL_DIR = Path(__file__).parents[3] / "autosearch/skills/channels/dockerhub/methods"


def _load_search():
    import importlib.util

    spec = importlib.util.spec_from_file_location("dockerhub_search", _SKILL_DIR / "api_search.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.search


@pytest.fixture()
def search():
    return _load_search()


@pytest.fixture()
def subquery():
    from autosearch.core.models import SubQuery

    return SubQuery(text="e2b sandbox", rationale="test")


_HUB_RESPONSE = {
    "results": [
        {
            "repo_name": "e2b/sandbox",
            "short_description": "E2B code execution sandbox",
            "pull_count": 500000,
            "star_count": 1200,
            "is_official": False,
        },
        {
            "repo_name": "library/python",
            "short_description": "Official Python image",
            "pull_count": 1000000000,
            "star_count": 15000,
            "is_official": True,
        },
    ]
}


@pytest.mark.asyncio()
async def test_search_returns_evidence(search, subquery):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.json.return_value = _HUB_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search(subquery)

    assert len(results) == 2
    assert results[0].source_channel == "dockerhub"
    assert "pulls:" in (results[0].snippet or "")
    assert "[Official]" in results[1].title


@pytest.mark.asyncio()
async def test_search_returns_empty_on_error(search, subquery):
    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("connection refused"),
    ):
        results = await search(subquery)

    assert results == []


@pytest.mark.asyncio()
async def test_search_skips_items_without_repo_name(search, subquery):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.json.return_value = {"results": [{"short_description": "no name"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search(subquery)

    assert results == []
