"""Tests for tieba channel."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

_SKILL_DIR = Path(__file__).parents[3] / "autosearch/skills/channels/tieba/methods"


def _load_search():
    import importlib.util

    spec = importlib.util.spec_from_file_location("tieba_search", _SKILL_DIR / "api_search.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.search


@pytest.fixture()
def search():
    return _load_search()


@pytest.fixture()
def subquery():
    from autosearch.core.models import SubQuery

    return SubQuery(text="Cursor 编程助手", rationale="test")


_TIEBA_HTML = """
<html><body>
<a href="/p/123456789" class="bleat_link" title="">Cursor AI 编程助手使用体验分享</a>
<a href="/p/987654321" class="bleat_link">关于 Cursor 和 VSCode 的对比讨论帖</a>
<a href="/p/111222333">Cursor 免费版限制问题汇总</a>
</body></html>
"""


@pytest.mark.asyncio()
async def test_search_returns_evidence(search, subquery):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.text = _TIEBA_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search(subquery)

    assert len(results) >= 2
    assert results[0].source_channel == "tieba"
    assert "tieba.baidu.com/p/" in results[0].url
    assert len(results[0].title) > 3


@pytest.mark.asyncio()
async def test_search_returns_empty_on_http_error(search, subquery):
    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("refused"),
    ):
        results = await search(subquery)

    assert results == []


@pytest.mark.asyncio()
async def test_search_deduplicates_urls(search, subquery):
    html = """
    <a href="/p/123">贴一</a>
    <a href="/p/123">贴一重复</a>
    <a href="/p/456">贴二</a>
    """
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await search(subquery)

    urls = [r.url for r in results]
    assert len(urls) == len(set(urls))
