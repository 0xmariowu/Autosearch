"""Tests for channels/_engines/ddgs.py with mocked ddgs package."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lib.search_runner import SearchError


def _make_ddgs_results(count: int = 3) -> list[dict]:
    return [
        {
            "href": f"https://example.com/{i}",
            "title": f"Result {i}",
            "body": f"Body {i}",
        }
        for i in range(count)
    ]


class TestDdgsSuccess:
    @pytest.mark.asyncio
    async def test_returns_results(self) -> None:
        from channels._engines.ddgs import search_ddgs_web

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = _make_ddgs_results(3)
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

        with patch("ddgs.DDGS", return_value=mock_ddgs_instance):
            results = await search_ddgs_web("test query", max_results=3)

        assert len(results) == 3
        assert results[0]["title"] == "Result 0"
        assert results[0]["source"] == "web-ddgs"

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        from channels._engines.ddgs import search_ddgs_web

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = []
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

        with patch("ddgs.DDGS", return_value=mock_ddgs_instance):
            results = await search_ddgs_web("obscure query")

        assert results == []


class TestDdgsError:
    @pytest.mark.asyncio
    async def test_exception_raises_search_error(self) -> None:
        from channels._engines.ddgs import search_ddgs_web

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = Exception("DDGS rate limited")
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

        with patch("ddgs.DDGS", return_value=mock_ddgs_instance):
            with pytest.raises(SearchError) as exc_info:
                await search_ddgs_web("test")

        assert exc_info.value.engine == "ddgs"
        assert exc_info.value.error_type == "network"


class TestDdgsSiteSearch:
    @pytest.mark.asyncio
    async def test_site_filter_prepends_site(self) -> None:
        from channels._engines.ddgs import search_ddgs_site

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = _make_ddgs_results(1)
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

        with patch("ddgs.DDGS", return_value=mock_ddgs_instance):
            results = await search_ddgs_site("test", "reddit.com", max_results=1)

        assert len(results) == 1
        # Verify site: was prepended to query
        call_args = mock_ddgs_instance.text.call_args
        assert "site:reddit.com" in call_args[0][0]
