"""G2-T2: Tests for arxiv channel api_search method."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_SKILL_DIR = Path(__file__).parents[3] / "autosearch/skills/channels/arxiv/methods"


def _load_search():
    import importlib.util

    spec = importlib.util.spec_from_file_location("arxiv_search", _SKILL_DIR / "api_search.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Clear cache between tests
    mod._QUERY_CACHE.clear()
    return mod.search


@pytest.fixture()
def search():
    return _load_search()


@pytest.fixture()
def subquery():
    from autosearch.core.models import SubQuery

    return SubQuery(text="LLM evaluation methodology", rationale="test")


_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>ArXiv Query: LLM evaluation</title>
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <title>A Survey of LLM Evaluation Methods</title>
    <summary>We survey recent methods for evaluating large language models.</summary>
    <author><name>Alice Smith</name></author>
    <published>2024-01-15T00:00:00Z</published>
    <link href="http://arxiv.org/abs/2401.12345v1" rel="alternate" type="text/html"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.99999v1</id>
    <title>Benchmarking LLMs on Reasoning Tasks</title>
    <summary>We introduce a new benchmark for LLM reasoning.</summary>
    <author><name>Bob Jones</name></author>
    <published>2024-02-01T00:00:00Z</published>
    <link href="http://arxiv.org/abs/2402.99999v1" rel="alternate" type="text/html"/>
  </entry>
</feed>"""


@pytest.mark.asyncio()
async def test_search_returns_evidence(search, subquery):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.text = _ATOM_XML
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search(subquery)

    assert len(results) >= 1
    assert results[0].source_channel == "arxiv"
    assert "arxiv.org" in results[0].url
    assert results[0].title


@pytest.mark.asyncio()
async def test_search_returns_empty_on_http_error(search, subquery):
    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.HTTPStatusError("500", request=None, response=None),
    ):
        results = await search(subquery)

    assert results == []


@pytest.mark.asyncio()
async def test_search_returns_empty_on_rate_limit(search, subquery):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.text = "Rate exceeded."
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search(subquery)

    assert results == []
