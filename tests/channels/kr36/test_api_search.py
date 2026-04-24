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
    <div class="search-result">
      <div class="article-item">
        <a class="article-item-title" href="/p/1234567890">
          AI 芯片公司完成新一轮融资
        </a>
        <div class="article-item-description">
          聚焦边缘推理与国产化部署，市场竞争开始加速。
        </div>
        <span class="article-author">36氪编辑部</span>
      </div>
      <div class="article-item">
        <a class="article-item-title" href="https://www.36kr.com/p/2222222222">
          具身智能 <em>机器人</em> 进入工厂
        </a>
        <div class="article-item-description">
          这是一段关于 <em>机器人</em> 进入制造场景的摘要。
        </div>
        <span class="article-author">李响</span>
      </div>
      <div class="article-item">
        <a class="article-item-title" href="/p/3333333333">没有作者的文章</a>
        <div class="article-item-description">只有摘要，没有作者信息。</div>
      </div>
    </div>
  </body>
</html>
"""

FIRST_ARTICLE_MARKDOWN = (
    "# AI 芯片公司完成新一轮融资\n\n" + "边缘推理、国产算力与交付能力正在同步提升。 " * 20
).strip()
SECOND_ARTICLE_MARKDOWN = (
    "## 具身智能 *机器人* 进入工厂\n\n" + "机器人团队开始进入制造、物流与质检等复杂环节。 " * 20
).strip()
THIRD_ARTICLE_MARKDOWN = (
    "## 没有作者的文章\n\n" + "文章正文提供了更完整的背景信息。 " * 20
).strip()


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "kr36"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_kr36_api_search", module_path)
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
    return SubQuery(text="AI 芯片", rationale="Need Chinese tech media coverage")


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
    if url.endswith("1234567890"):
        return FIRST_ARTICLE_MARKDOWN
    if url.endswith("2222222222"):
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
async def test_search_maps_article_items_to_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_urls: list[str] = []
    captured_clients: list[httpx.AsyncClient | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["searchType"] == "post"
        assert request.url.params["q"] == "AI 芯片"
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
    assert first.title == "AI 芯片公司完成新一轮融资"
    assert first.snippet == FIRST_ARTICLE_MARKDOWN[:300]
    assert len(first.snippet or "") == 300
    assert first.content == FIRST_ARTICLE_MARKDOWN
    assert first.source_channel == "kr36:36氪编辑部"
    assert first.source_page is not None
    assert first.source_page.markdown == FIRST_ARTICLE_MARKDOWN

    second = results[1]
    assert second.title == "具身智能 机器人 进入工厂"
    assert second.snippet == SECOND_ARTICLE_MARKDOWN[:300]
    assert "<em>" not in (second.snippet or "")
    assert "*机器人*" in (second.snippet or "")
    assert second.content == SECOND_ARTICLE_MARKDOWN
    assert second.source_channel == "kr36:李响"
    assert captured_urls == [
        "https://www.36kr.com/p/1234567890",
        "https://www.36kr.com/p/2222222222",
        "https://www.36kr.com/p/3333333333",
    ]
    assert all(client is http_client for client in captured_clients)


@pytest.mark.asyncio
async def test_search_handles_relative_href(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SEARCH_PAGE_HTML, request=request)

    _patch_fetch_page(monkeypatch)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results[0].url == "https://www.36kr.com/p/1234567890"


@pytest.mark.asyncio
async def test_search_handles_missing_author(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SEARCH_PAGE_HTML, request=request)

    _patch_fetch_page(monkeypatch)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results[2].source_channel == "kr36"


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
        error_urls={"https://www.36kr.com/p/1234567890"},
        markdown_by_url={
            "https://www.36kr.com/p/2222222222": SECOND_ARTICLE_MARKDOWN,
            "https://www.36kr.com/p/3333333333": THIRD_ARTICLE_MARKDOWN,
        },
    )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 3
    assert results[0].snippet == "聚焦边缘推理与国产化部署，市场竞争开始加速。"
    assert results[0].content == "聚焦边缘推理与国产化部署，市场竞争开始加速。"
    assert results[0].source_page is None
    assert results[1].snippet == SECOND_ARTICLE_MARKDOWN[:300]
    assert results[1].source_page is not None
    assert logger.events == [
        (
            "kr36_result_fetch_failed",
            {
                "url": "https://www.36kr.com/p/1234567890",
                "reason": "html fetch failed: timeout (url=https://www.36kr.com/p/1234567890, status=None)",
            },
        )
    ]


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autosearch.channels.base import TransientError

    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway", request=request)

    async with _client(handler) as http_client:
        with pytest.raises(TransientError):
            await search(_query(), http_client=http_client)

    assert logger.events == [
        (
            "kr36_search_failed",
            {
                "reason": (
                    "html fetch failed: http_error (url=https://www.36kr.com/search, status=502)"
                )
            },
        )
    ]


@pytest.mark.asyncio
async def test_search_returns_empty_on_no_results() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="<html><body>no article items</body></html>", request=request
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
