"""Tests for pubmed channel."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_SKILL_DIR = Path(__file__).parents[3] / "autosearch/skills/channels/pubmed/methods"


def _load_search():
    import importlib.util

    spec = importlib.util.spec_from_file_location("pubmed_search", _SKILL_DIR / "api_search.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.search


@pytest.fixture()
def search():
    return _load_search()


@pytest.fixture()
def subquery():
    from autosearch.core.models import SubQuery

    return SubQuery(text="LLM evaluation methodology", rationale="test")


_ESEARCH_RESPONSE = {"esearchresult": {"idlist": ["12345678", "87654321"]}}
_ESUMMARY_RESPONSE = {
    "result": {
        "uids": ["12345678"],
        "12345678": {
            "uid": "12345678",
            "title": "A systematic review of LLM evaluation",
            "source": "Nature Machine Intelligence",
            "pubdate": "2024",
            "authors": [{"name": "Smith J"}, {"name": "Doe A"}],
            "articleids": [{"idtype": "doi", "value": "10.1234/test"}],
        },
    }
}


@pytest.mark.asyncio()
async def test_search_returns_evidence(search, subquery):
    with (
        patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[
                _mock_response(_ESEARCH_RESPONSE),
                _mock_response(_ESUMMARY_RESPONSE),
            ],
        ),
    ):
        results = await search(subquery)

    assert len(results) >= 1
    assert results[0].source_channel == "pubmed"
    assert "LLM evaluation" in results[0].title
    assert "10.1234/test" in (results[0].snippet or "")


@pytest.mark.asyncio()
async def test_search_returns_empty_on_no_ids(search, subquery):
    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=_mock_response({"esearchresult": {"idlist": []}}),
    ):
        results = await search(subquery)

    assert results == []


@pytest.mark.asyncio()
async def test_search_returns_empty_on_http_error(search, subquery):
    # Bug 1 (fix-plan): typed exception now propagates instead of [].
    from autosearch.channels.base import (
        ChannelAuthError,
        PermanentError,
        RateLimited,
        TransientError,
    )

    import httpx

    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.HTTPStatusError("error", request=None, response=None),
    ):
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(subquery)


def _mock_response(data: dict):
    import httpx
    from unittest.mock import MagicMock

    resp = MagicMock(spec=httpx.Response)
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp
