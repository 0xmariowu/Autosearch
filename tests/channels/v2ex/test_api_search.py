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
        / "v2ex"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_v2ex_api_search", module_path)
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
    return SubQuery(text="react hooks", rationale="Need V2EX developer discussion coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_v2ex_hits_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "react hooks"
        assert request.url.params["size"] == "10"
        return httpx.Response(
            200,
            json={
                "took": 5,
                "total": 2,
                "hits": [
                    {
                        "_id": "630175",
                        "_source": {
                            "id": 630175,
                            "title": "大家写 React 项目都用 React hooks 吗",
                            "content": "我感觉 React hooks 更适合颗粒度小的组件。",
                        },
                    },
                    {
                        "_id": "630176",
                        "_source": {
                            "id": 630176,
                            "title": "另一篇讨论",
                            "content": "这里有更多关于状态管理和组件拆分的经验。",
                        },
                    },
                ],
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://www.v2ex.com/t/630175"
    assert first.title == "大家写 React 项目都用 React hooks 吗"
    assert first.snippet == "我感觉 React hooks 更适合颗粒度小的组件。"
    assert first.content == "我感觉 React hooks 更适合颗粒度小的组件。"
    assert first.source_channel == "v2ex"

    second = results[1]
    assert second.url == "https://www.v2ex.com/t/630176"
    assert second.title == "另一篇讨论"
    assert second.snippet == "这里有更多关于状态管理和组件拆分的经验。"
    assert second.content == "这里有更多关于状态管理和组件拆分的经验。"
    assert second.source_channel == "v2ex"


@pytest.mark.asyncio
async def test_search_skips_hits_without_source() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": [
                    {"_id": "missing-source"},
                    {
                        "_id": "630177",
                        "_source": {
                            "id": 630177,
                            "title": "有效帖子",
                            "content": "保留这个结果。",
                        },
                    },
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://www.v2ex.com/t/630177"


@pytest.mark.asyncio
async def test_search_skips_hits_without_thread_id() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "_id": "missing-id",
                        "_source": {
                            "title": "没有 id 的帖子",
                            "content": "这个结果应该被跳过。",
                        },
                    },
                    {
                        "_id": "630178",
                        "_source": {
                            "id": 630178,
                            "title": "保留下来的帖子",
                            "content": "这个结果应该保留。",
                        },
                    },
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://www.v2ex.com/t/630178"


@pytest.mark.asyncio
async def test_search_falls_back_to_content_excerpt_when_title_empty() -> None:
    content = "x" * 70

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "_id": "630179",
                        "_source": {
                            "id": 630179,
                            "title": "   ",
                            "content": content,
                        },
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == f"{'x' * 60}…"


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "v2ex_search_failed"
    assert "500" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_truncates_snippet_at_300_chars() -> None:
    content = ("word " * 60) + "tail beyond the snippet limit"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "_id": "630180",
                        "_source": {
                            "id": 630180,
                            "title": "Long content thread",
                            "content": content,
                        },
                    }
                ]
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].snippet == f"{('word ' * 60).strip()}…"
    assert results[0].content == content
