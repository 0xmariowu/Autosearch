"""Unit tests for Chinese channel native API implementations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# --- Cookie auth ---


def test_parse_cookie_string():
    from channels._engines.cookie_auth import _parse_cookie_string

    assert _parse_cookie_string("z_c0=abc; d_c0=def") == {"z_c0": "abc", "d_c0": "def"}
    assert _parse_cookie_string("") == {}
    assert _parse_cookie_string("noequals") == {}


def test_has_cookies():
    from channels._engines.cookie_auth import has_cookies

    assert has_cookies({"z_c0": "x", "d_c0": "y"}, ["z_c0"]) is True
    assert has_cookies({"d_c0": "y"}, ["z_c0"]) is False
    assert has_cookies(None, ["z_c0"]) is False


def test_cookie_header():
    from channels._engines.cookie_auth import cookie_header

    result = cookie_header({"a": "1", "b": "2"})
    assert "a=1" in result and "b=2" in result


# --- Baidu URL filter ---


@pytest.mark.asyncio
async def test_baidu_filters_off_site_results():
    """Baidu drops results whose URL doesn't match target site."""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "data": {
            "documents": {
                "data": [
                    {
                        "techDocDigest": {
                            "title": "On-site",
                            "url": "https://36kr.com/p/123",
                            "summary": "good",
                        }
                    },
                    {
                        "techDocDigest": {
                            "title": "Off-site",
                            "url": "https://csdn.net/article/456",
                            "summary": "bad",
                        }
                    },
                    {
                        "techDocDigest": {
                            "title": "Also on",
                            "url": "https://www.36kr.com/p/789",
                            "summary": "good2",
                        }
                    },
                ]
            }
        }
    }
    fake_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=fake_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from channels._engines.baidu import search_baidu

        results = await search_baidu("test", site="36kr.com", max_results=10)

    assert len(results) == 2
    assert all("36kr.com" in r["url"] for r in results)


# --- CSDN ---


@pytest.mark.asyncio
async def test_csdn_native_parses_results():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.is_error = False
    fake_resp.json.return_value = {
        "result_vos": [
            {
                "url": "https://blog.csdn.net/user/article/details/123",
                "title": "Test <em>AI</em>",
                "description": "About <em>AI</em>.",
                "view_num": 5000,
                "nickname": "author1",
            }
        ]
    }
    fake_resp.raise_for_status = MagicMock()

    mock_article = MagicMock()
    mock_article.status_code = 200
    mock_article.is_error = False
    mock_article.text = '<div id="article_content">Long article content here that is definitely more than one hundred characters to pass the length check in the extraction logic and provide real value.</div>'

    async def fake_get(url, **kw):
        if "so.csdn.net" in url:
            return fake_resp
        return mock_article

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from channels.csdn.search import search

        results = await search("AI", max_results=5)

    assert len(results) == 1
    assert results[0]["source"] == "csdn"
    assert "AI" in results[0]["title"]
    assert results[0]["metadata"]["views"] == 5000
    assert results[0]["metadata"].get("extracted_content")


@pytest.mark.asyncio
async def test_csdn_falls_back_to_baidu():
    """CSDN uses Baidu fallback when native API errors."""
    with patch(
        "channels.csdn.search._search_native",
        new_callable=AsyncMock,
        side_effect=Exception("API down"),
    ):
        with patch(
            "channels._engines.baidu.search_baidu",
            new_callable=AsyncMock,
            return_value=[{"title": "baidu"}],
        ) as mock_baidu:
            from channels.csdn.search import search

            results = await search("test")
            mock_baidu.assert_called_once()
            assert results[0]["title"] == "baidu"


# --- Juejin ---


@pytest.mark.asyncio
async def test_juejin_native_parses_results():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "err_no": 0,
        "data": [
            {
                "result_model": {
                    "article_info": {
                        "article_id": "123",
                        "title": "AI Agent",
                        "brief_content": "About AI",
                    },
                    "author_user_info": {"user_name": "author1"},
                    "tags": [{"tag_name": "AI"}],
                }
            }
        ],
    }
    fake_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=fake_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from channels.juejin.search import search

        results = await search("AI", max_results=5)

    assert len(results) == 1
    assert "juejin.cn/post/123" in results[0]["url"]
    assert results[0]["metadata"]["author"] == "author1"
    assert results[0]["metadata"]["tags"] == ["AI"]


# --- 36kr ---


@pytest.mark.asyncio
async def test_36kr_native_with_csrf():
    csrf_resp = MagicMock()
    csrf_resp.status_code = 200
    csrf_resp.cookies = httpx.Cookies()
    csrf_resp.cookies.set("M-XSRF-TOKEN", "test-token")

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {
        "code": 0,
        "data": {
            "itemList": [
                {
                    "itemId": "456",
                    "widgetTitle": "AI article",
                    "summary": "About AI",
                    "publishTime": 1775372371211,
                }
            ],
            "totalNum": 1,
        },
    }
    search_resp.raise_for_status = MagicMock()

    article_resp = MagicMock()
    article_resp.status_code = 200
    article_resp.is_error = False
    article_resp.text = '<script>window.initialState={"articleDetail":{"articleDetailData":{"data":{"widgetContent":"<p>Full article text that is definitely longer than one hundred characters to pass the extraction threshold check.</p>"}}}};</script>'

    async def fake_get(url, **kw):
        if "csrf" in url:
            return csrf_resp
        return article_resp

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.post = AsyncMock(return_value=search_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from importlib import import_module

        mod = import_module("channels.36kr.search")
        results = await mod.search("AI", max_results=5)

    assert len(results) == 1
    assert "36kr.com/p/456" in results[0]["url"]
    assert results[0]["metadata"].get("extracted_content")


# --- ENGINE_CHANNELS ---


def test_native_channels_not_in_baidu_group():
    from lib.search_runner import ENGINE_CHANNELS

    baidu = ENGINE_CHANNELS.get("baidu", [])
    for ch in ["csdn", "36kr", "juejin", "weibo"]:
        assert ch not in baidu, f"{ch} should not be in baidu group"
    for ch in ["douyin", "xiaoyuzhou"]:
        assert ch in baidu, f"{ch} should remain in baidu group"


# --- Zhihu fallback ---


@pytest.mark.asyncio
async def test_zhihu_falls_back_without_cookie():
    with patch("channels._engines.cookie_auth.get_cookies", return_value=None):
        with patch(
            "channels._engines.baidu.search_baidu",
            new_callable=AsyncMock,
            return_value=[{"title": "baidu zhihu"}],
        ):
            from channels.zhihu.search import search

            results = await search("AI")
            assert results[0]["title"] == "baidu zhihu"


# --- Weibo fallback ---


@pytest.mark.asyncio
async def test_weibo_falls_back_without_cookie():
    with patch("channels._engines.cookie_auth.get_cookies", return_value=None):
        with patch(
            "channels._engines.baidu.search_baidu",
            new_callable=AsyncMock,
            return_value=[{"title": "baidu weibo"}],
        ):
            from channels.weibo.search import search

            results = await search("AI")
            assert results[0]["title"] == "baidu weibo"
