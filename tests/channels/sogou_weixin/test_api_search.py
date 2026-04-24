# Self-written for task F204
from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

from autosearch.core.models import FetchedPage, SubQuery
from autosearch.lib.html_scraper import HtmlFetchError

SEARCH_PAGE_HTML = """
<html>
  <body>
    <ul class="news-list">
      <li id="sogou_vr_11002601">
        <div class="txt-box">
          <h3>
            <a href="https://mp.weixin.qq.com/s/example-1">
              AI <em>芯片</em> 创业公司拿下新融资
            </a>
          </h3>
          <p class="txt-info">
            这是一段关于 <em>芯片</em> 创业公司的摘要，包含最新进展与市场判断。
          </p>
          <div class="s-p">
            <a class="account" href="/gzh?openid=o123">极客公园</a>
            <span>2026-04-10</span>
          </div>
        </div>
      </li>
      <li id="sogou_vr_11002602">
        <div class="txt-box">
          <h3>
            <a href="/link?url=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fexample-2">
              企业服务 <em>出海</em> 怎么做
            </a>
          </h3>
          <p class="txt-info">
            面向 B2B 团队的 <em>出海</em> 操作清单与避坑经验。
          </p>
          <div class="s-p">
            <a class="account" href="/gzh?openid=o456">晚点团队</a>
            <span>2026-04-11</span>
          </div>
        </div>
      </li>
      <li id="sogou_vr_11002603">
        <div class="txt-box">
          <h3><a href="https://mp.weixin.qq.com/s/example-3">没有账号名的结果</a></h3>
          <p class="txt-info">只有摘要，没有公众号名。</p>
        </div>
      </li>
    </ul>
  </body>
</html>
"""

FIRST_ARTICLE_MARKDOWN = (
    "# AI *芯片* 创业公司拿下新融资\n\n" + "芯片公司完成新融资，开始推进量产和客户验证。 " * 20
).strip()
SECOND_ARTICLE_MARKDOWN = (
    "## 企业服务 *出海* 怎么做\n\n" + "出海团队需要梳理渠道、合规与交付节奏。 " * 20
).strip()
THIRD_ARTICLE_MARKDOWN = ("## 没有账号名的结果\n\n" + "文章正文补充了更多背景信息。 " * 20).strip()


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "sogou_weixin"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_sogou_weixin_api_search", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
search = MODULE.search


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _query() -> SubQuery:
    return SubQuery(text="AI 芯片", rationale="Need Chinese public account coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _fetched_page(url: str, *, markdown: str) -> FetchedPage:
    return FetchedPage(
        url=url,
        status_code=200,
        html="<html></html>",
        cleaned_html="<article></article>",
        markdown=markdown,
    )


def _default_markdown_for_url(url: str) -> str:
    if url.endswith("example-1"):
        return FIRST_ARTICLE_MARKDOWN
    if url.endswith("example-2"):
        return SECOND_ARTICLE_MARKDOWN
    return THIRD_ARTICLE_MARKDOWN


def _patch_fetch_page(
    monkeypatch: pytest.MonkeyPatch,
    *,
    markdown_by_url: dict[str, str] | None = None,
    error_urls: set[str] | None = None,
) -> None:
    async def fake_fetch_page(
        url: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> FetchedPage:
        _ = client
        if error_urls and url in error_urls:
            raise HtmlFetchError(url, reason="timeout")
        markdown = (markdown_by_url or {}).get(url, _default_markdown_for_url(url))
        return _fetched_page(url, markdown=markdown)

    monkeypatch.setattr(MODULE, "fetch_page", fake_fetch_page)


@pytest.mark.asyncio
async def test_search_maps_li_blocks_to_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_urls: list[str] = []
    captured_clients: list[httpx.AsyncClient | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["type"] == "2"
        assert request.url.params["query"] == "AI 芯片"
        return httpx.Response(200, text=SEARCH_PAGE_HTML, request=request)

    async def fake_fetch_page(
        url: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> FetchedPage:
        captured_urls.append(url)
        captured_clients.append(client)
        return _fetched_page(url, markdown=_default_markdown_for_url(url))

    monkeypatch.setattr(MODULE, "fetch_page", fake_fetch_page)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 3

    first = results[0]
    assert first.url == "https://mp.weixin.qq.com/s/example-1"
    assert first.title == "AI 芯片 创业公司拿下新融资"
    assert first.snippet == FIRST_ARTICLE_MARKDOWN[:300]
    assert len(first.snippet or "") == 300
    assert first.content == FIRST_ARTICLE_MARKDOWN
    assert first.source_channel == "sogou_weixin:极客公园"
    assert first.source_page is not None
    assert first.source_page.markdown == FIRST_ARTICLE_MARKDOWN

    second = results[1]
    assert second.title == "企业服务 出海 怎么做"
    assert second.snippet == SECOND_ARTICLE_MARKDOWN[:300]
    assert second.content == SECOND_ARTICLE_MARKDOWN
    assert second.source_channel == "sogou_weixin:晚点团队"
    assert captured_urls == [
        "https://mp.weixin.qq.com/s/example-1",
        "https://weixin.sogou.com/link?url=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fexample-2",
        "https://mp.weixin.qq.com/s/example-3",
    ]
    assert all(client is http_client for client in captured_clients)


@pytest.mark.asyncio
async def test_search_strips_em_markers_from_title_and_snippet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SEARCH_PAGE_HTML, request=request)

    _patch_fetch_page(
        monkeypatch,
        markdown_by_url={
            "https://mp.weixin.qq.com/s/example-1": FIRST_ARTICLE_MARKDOWN,
            "https://weixin.sogou.com/link?url=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fexample-2": SECOND_ARTICLE_MARKDOWN,
        },
    )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) >= 2
    assert "<em>" not in results[0].title
    assert "<em>" not in (results[0].snippet or "")
    assert "<em>" not in (results[1].snippet or "")
    assert "芯片" in results[0].title
    assert "*芯片*" in (results[0].snippet or "")
    assert "*出海*" in (results[1].snippet or "")


@pytest.mark.asyncio
async def test_search_handles_link_redirect_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SEARCH_PAGE_HTML, request=request)

    _patch_fetch_page(monkeypatch)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert (
        results[1].url
        == "https://weixin.sogou.com/link?url=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fexample-2"
    )


@pytest.mark.asyncio
async def test_search_handles_missing_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SEARCH_PAGE_HTML, request=request)

    _patch_fetch_page(monkeypatch)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results[2].source_channel == "sogou_weixin"


@pytest.mark.asyncio
async def test_search_falls_back_to_listing_snippet_on_fetch_page_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SEARCH_PAGE_HTML, request=request)

    _patch_fetch_page(
        monkeypatch,
        error_urls={"https://mp.weixin.qq.com/s/example-1"},
        markdown_by_url={
            "https://weixin.sogou.com/link?url=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fexample-2": SECOND_ARTICLE_MARKDOWN,
            "https://mp.weixin.qq.com/s/example-3": THIRD_ARTICLE_MARKDOWN,
        },
    )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 3
    assert results[0].snippet == "这是一段关于 芯片 创业公司的摘要，包含最新进展与市场判断。"
    assert results[0].content == "这是一段关于 芯片 创业公司的摘要，包含最新进展与市场判断。"
    assert results[0].source_page is None
    assert results[1].snippet == SECOND_ARTICLE_MARKDOWN[:300]
    assert results[1].source_page is not None
    assert logger.events == [
        (
            "sogou_weixin_result_fetch_failed",
            {
                "url": "https://mp.weixin.qq.com/s/example-1",
                "reason": "html fetch failed: timeout (url=https://mp.weixin.qq.com/s/example-1, status=None)",
            },
        )
    ]


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Bug 1 (fix-plan): typed exception now propagates instead of [].
    from autosearch.channels.base import (
        ChannelAuthError,
        PermanentError,
        RateLimited,
        TransientError,
    )

    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden", request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events == [
        (
            "sogou_weixin_search_failed",
            {
                "reason": (
                    "html fetch failed: http_error "
                    "(url=https://weixin.sogou.com/weixin, status=403)"
                )
            },
        )
    ]


@pytest.mark.asyncio
async def test_search_returns_empty_on_empty_html() -> None:
    # Empty HTML is a legit "no matches" — channel returns [] without raising.
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>no results</body></html>", request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
