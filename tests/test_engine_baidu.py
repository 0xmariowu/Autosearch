"""Tests for channels/_engines/baidu.py with mocked httpx."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.search_runner import SearchError


def _make_baidu_response(docs: list[dict], status: int = 200) -> MagicMock:
    """Create a mock httpx response for Baidu Kaifa API."""
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    resp.json.return_value = {
        "data": {
            "documents": {
                "data": [
                    {
                        "techDocDigest": {
                            "title": d.get("title", ""),
                            "url": d.get("url", ""),
                            "summary": d.get("summary", ""),
                        }
                    }
                    for d in docs
                ]
            }
        }
    }
    return resp


class TestBaiduSuccess:
    @pytest.mark.asyncio
    async def test_returns_results(self) -> None:
        from channels._engines.baidu import search_baidu

        mock_resp = _make_baidu_response(
            [
                {
                    "title": "Test Title",
                    "url": "https://example.com",
                    "summary": "A snippet",
                },
            ]
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "channels._engines.baidu.httpx.AsyncClient", return_value=mock_client
        ):
            results = await search_baidu("test query")

        assert len(results) == 1
        assert results[0]["title"] == "Test Title"
        assert results[0]["source"] == "baidu"

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        from channels._engines.baidu import search_baidu

        mock_resp = _make_baidu_response([])
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "channels._engines.baidu.httpx.AsyncClient", return_value=mock_client
        ):
            results = await search_baidu("niche query")

        assert results == []

    @pytest.mark.asyncio
    async def test_site_filter(self) -> None:
        from channels._engines.baidu import search_baidu

        mock_resp = _make_baidu_response(
            [
                {
                    "title": "Zhihu Post",
                    "url": "https://zhihu.com/p/123",
                    "summary": "content",
                },
            ]
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "channels._engines.baidu.httpx.AsyncClient", return_value=mock_client
        ):
            results = await search_baidu("test", site="zhihu.com")

        assert len(results) == 1
        assert results[0]["source"] == "zhihu"
        # Verify site: prefix was added to query
        call_kwargs = mock_client.get.call_args
        assert "site:zhihu.com" in call_kwargs.kwargs.get("params", {}).get("wd", "")


class TestBaiduError:
    @pytest.mark.asyncio
    async def test_api_error_raises_search_error(self) -> None:
        from channels._engines.baidu import search_baidu

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "channels._engines.baidu.httpx.AsyncClient", return_value=mock_client
        ):
            with pytest.raises(SearchError) as exc_info:
                await search_baidu("test")

        assert exc_info.value.engine == "baidu"
        assert exc_info.value.error_type == "network"
