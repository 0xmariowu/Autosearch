# Self-written for task F204
from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

from autosearch.core.models import SubQuery

HTML_FIXTURE = """
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


@pytest.mark.asyncio
async def test_search_maps_article_items_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["searchType"] == "post"
        assert request.url.params["q"] == "AI 芯片"
        return httpx.Response(200, text=HTML_FIXTURE, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 3

    first = results[0]
    assert first.title == "AI 芯片公司完成新一轮融资"
    assert first.snippet == "聚焦边缘推理与国产化部署，市场竞争开始加速。"
    assert first.content == first.snippet
    assert first.source_channel == "kr36:36氪编辑部"

    second = results[1]
    assert second.title == "具身智能 机器人 进入工厂"
    assert second.snippet == "这是一段关于 机器人 进入制造场景的摘要。"
    assert second.source_channel == "kr36:李响"


@pytest.mark.asyncio
async def test_search_handles_relative_href() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=HTML_FIXTURE, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results[0].url == "https://www.36kr.com/p/1234567890"


@pytest.mark.asyncio
async def test_search_handles_missing_author() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=HTML_FIXTURE, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results[2].source_channel == "kr36"


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway", request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
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
