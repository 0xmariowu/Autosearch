from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

from autosearch.core.models import SubQuery


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "discourse_forum"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_discourse_forum_api_search", module_path)
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
    return SubQuery(text="claude code", rationale="Need Linux DO and Discourse forum coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_discourse_posts_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://linux.do/search.json?q=claude+code":
            return httpx.Response(
                200,
                json={
                    "posts": [
                        {
                            "topic_id": 1799314,
                            "topic_title_headline": 'Claude <span class="search-highlight">Code</span> 对非官方 API 的功能限制分析',
                            "blurb": '这里整理了 <span class="search-highlight">Claude</span> Code 与 Tool Search 的实际限制。',
                        },
                        {
                            "topic_id": 1064521,
                            "topic_title_headline": "LinuxDo 批量检索导出",
                            "blurb": "搜索话题并批量拉取全文后导出。",
                        },
                    ]
                },
                request=request,
            )
        if str(request.url) == "https://r.jina.ai/https://linux.do/t/1799314":
            return httpx.Response(
                200,
                text=(
                    "Title: Claude Code 对非官方 API 的功能限制分析 - LINUX DO\n\n"
                    "URL Source: https://linux.do/t/1799314\n\n"
                    "Markdown Content:\n"
                    "完整正文第一段。\n\n完整正文第二段。"
                ),
                request=request,
            )
        if str(request.url) == "https://r.jina.ai/https://linux.do/t/1064521":
            return httpx.Response(
                200,
                text=(
                    "Title: LinuxDo 批量检索导出 - LINUX DO\n\n"
                    "URL Source: https://linux.do/t/1064521\n\n"
                    "Markdown Content:\n"
                    "导出帖子的完整内容。"
                ),
                request=request,
            )
        raise AssertionError(f"Unexpected URL: {request.url}")

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://linux.do/t/1799314"
    assert first.title == "Claude Code 对非官方 API 的功能限制分析"
    assert first.snippet == "完整正文第一段。 完整正文第二段。"
    assert first.content == "完整正文第一段。\n\n完整正文第二段。"
    assert first.source_channel == "discourse_forum:linux_do"
    assert first.source_page is not None
    assert first.source_page.url == "https://linux.do/t/1799314"
    assert first.source_page.status_code == 200
    assert first.source_page.markdown == "完整正文第一段。\n\n完整正文第二段。"
    assert first.source_page.metadata == {
        "reader_url": "https://r.jina.ai/https://linux.do/t/1799314",
        "title": "Claude Code 对非官方 API 的功能限制分析",
    }

    second = results[1]
    assert second.url == "https://linux.do/t/1064521"
    assert second.title == "LinuxDo 批量检索导出"
    assert second.content == "导出帖子的完整内容。"


@pytest.mark.asyncio
async def test_search_deduplicates_multiple_posts_from_same_topic() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "posts": [
                    {
                        "topic_id": 1799314,
                        "topic_title_headline": "Same topic",
                        "blurb": "First blurb",
                    },
                    {
                        "topic_id": 1799314,
                        "topic_title_headline": "Same topic duplicate",
                        "blurb": "Second blurb",
                    },
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://linux.do/t/1799314"
    assert results[0].title == "Same topic"


@pytest.mark.asyncio
async def test_search_skips_posts_without_topic_id() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "posts": [
                    {
                        "topic_title_headline": "Missing topic id",
                        "blurb": "Cannot build canonical URL",
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []


@pytest.mark.asyncio
async def test_search_uses_slug_canonical_topic_url_for_enrichment() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://linux.do/search.json?q=claude+code":
            return httpx.Response(
                200,
                json={
                    "posts": [
                        {
                            "topic_id": 760680,
                            "slug": "claude-code-shang-shou-zhi-nan",
                            "topic_title_headline": 'Claude <span class="search-highlight">Code</span> 上手指南',
                            "blurb": "帖子摘要。",
                        }
                    ]
                },
                request=request,
            )
        if (
            str(request.url)
            == "https://r.jina.ai/https://linux.do/t/claude-code-shang-shou-zhi-nan/760680"
        ):
            return httpx.Response(
                200,
                text=(
                    "Title: Claude Code 上手指南 - LINUX DO\n\n"
                    "URL Source: https://linux.do/t/claude-code-shang-shou-zhi-nan/760680\n\n"
                    "Markdown Content:\n"
                    "这里是完整正文。"
                ),
                request=request,
            )
        raise AssertionError(f"Unexpected URL: {request.url}")

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://linux.do/t/claude-code-shang-shou-zhi-nan/760680"
    assert results[0].snippet == "这里是完整正文。"
    assert results[0].content == "这里是完整正文。"
    assert results[0].source_page is not None
    assert results[0].source_page.metadata == {
        "reader_url": "https://r.jina.ai/https://linux.do/t/claude-code-shang-shou-zhi-nan/760680",
        "title": "Claude Code 上手指南",
    }


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)
    monkeypatch.setattr(MODULE, "DDGS", lambda: (_ for _ in ()).throw(Exception("ddgs blocked")))

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "discourse_forum_search_failed"
    assert "403" in str(logger.events[0][1]["reason"])
    assert logger.events[0][1]["fallback_reason"] == "ddgs blocked"


@pytest.mark.asyncio
async def test_search_returns_empty_on_malformed_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)
    monkeypatch.setattr(MODULE, "DDGS", lambda: (_ for _ in ()).throw(Exception("ddgs blocked")))

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"topics": []}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events == [
        (
            "discourse_forum_search_failed",
            {"reason": "invalid posts payload", "fallback_reason": "ddgs blocked"},
        )
    ]


@pytest.mark.asyncio
async def test_search_falls_back_to_site_search_when_api_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeDDGS:
        def text(self, query: str, *, max_results: int):
            assert query == "site:linux.do claude code"
            assert max_results == 10
            return [
                {
                    "title": "LINUX DO - 新的理想型社区",
                    "href": "https://linux.do/latest",
                    "body": "This is only a topic list page and should be ignored.",
                },
                {
                    "title": "Claude Code 入门 - 开发调优 - LINUX DO",
                    "href": "https://linux.do/t/topic/1798141",
                    "body": "整理了 Claude Code 的上手经验和限制。",
                },
            ]

    monkeypatch.setattr(MODULE, "DDGS", _FakeDDGS)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://linux.do/t/topic/1798141"
    assert results[0].title == "Claude Code 入门 - 开发调优"
    assert results[0].snippet == "整理了 Claude Code 的上手经验和限制。"
    assert results[0].source_channel == "discourse_forum:linux_do:site_search"


@pytest.mark.asyncio
async def test_search_enriches_site_search_results_with_full_topic_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeDDGS:
        def text(self, query: str, *, max_results: int):
            assert query == "site:linux.do claude code"
            assert max_results == 10
            return [
                {
                    "title": "Claude Code 小白指引贴 - 文档共建 - LINUX DO",
                    "href": "https://linux.do/t/topic/743319",
                    "body": "搜索摘要不应该保留为最终正文。",
                }
            ]

    monkeypatch.setattr(MODULE, "DDGS", _FakeDDGS)

    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://linux.do/search.json?q=claude+code":
            return httpx.Response(403, json={"error": "forbidden"}, request=request)
        if str(request.url) == "https://r.jina.ai/https://linux.do/t/topic/743319":
            return httpx.Response(
                200,
                text=(
                    "Title: Claude Code 小白指引贴 - 文档共建 - LINUX DO\n\n"
                    "URL Source: https://linux.do/t/topic/743319\n\n"
                    "Markdown Content:\n"
                    "完整正文第一段。\n\n完整正文第二段。"
                ),
                request=request,
            )
        raise AssertionError(f"Unexpected URL: {request.url}")

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://linux.do/t/topic/743319"
    assert results[0].title == "Claude Code 小白指引贴 - 文档共建"
    assert results[0].snippet == "完整正文第一段。 完整正文第二段。"
    assert results[0].content == "完整正文第一段。\n\n完整正文第二段。"
    assert results[0].source_channel == "discourse_forum:linux_do:site_search"
    assert results[0].source_page is not None
    assert results[0].source_page.metadata == {
        "reader_url": "https://r.jina.ai/https://linux.do/t/topic/743319",
        "title": "Claude Code 小白指引贴 - 文档共建",
    }


@pytest.mark.asyncio
async def test_search_preserves_search_snippet_when_topic_enrichment_fails() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://linux.do/search.json?q=claude+code":
            return httpx.Response(
                200,
                json={
                    "posts": [
                        {
                            "topic_id": 1799314,
                            "topic_title_headline": "Search title",
                            "blurb": "Search summary only",
                        }
                    ]
                },
                request=request,
            )
        if str(request.url) == "https://r.jina.ai/https://linux.do/t/1799314":
            return httpx.Response(403, text="forbidden", request=request)
        raise AssertionError(f"Unexpected URL: {request.url}")

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "Search title"
    assert results[0].snippet == "Search summary only"
    assert results[0].content == "Search summary only"
    assert results[0].source_page is None
