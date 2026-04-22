"""G2-T4: Tests for ddgs channel api method."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import autosearch.skills.channels.ddgs.methods.api as ddgs_mod


@pytest.fixture()
def search():
    return ddgs_mod.search


@pytest.fixture()
def subquery():
    from autosearch.core.models import SubQuery

    return SubQuery(text="autosearch deep research tool", rationale="test")


_DDGS_RESULTS = [
    {
        "title": "AutoSearch Tool",
        "href": "https://example.com/autosearch",
        "body": "A deep research system.",
    },
    {
        "title": "AutoSearch GitHub",
        "href": "https://github.com/example/autosearch",
        "body": "Open source.",
    },
]


@pytest.mark.asyncio()
async def test_search_returns_evidence(search, subquery):
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = _DDGS_RESULTS

    with patch.object(ddgs_mod, "DDGS", return_value=mock_ddgs):
        results = await search(subquery)

    assert len(results) >= 1
    assert results[0].source_channel == "ddgs"
    assert results[0].url.startswith("http")
    assert results[0].title


@pytest.mark.asyncio()
async def test_search_returns_empty_on_exception(search, subquery):
    with patch.object(ddgs_mod, "DDGS", side_effect=Exception("network error")):
        results = await search(subquery)

    assert results == []
