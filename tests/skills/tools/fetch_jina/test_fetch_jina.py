from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import httpx
import pytest


def _load_fetch_jina() -> ModuleType:
    root = Path(__file__).resolve().parents[4]
    fetch_path = root / "autosearch" / "skills" / "tools" / "fetch-jina" / "fetch.py"
    spec = importlib.util.spec_from_file_location("fetch_jina_under_test", fetch_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FETCH_JINA = _load_fetch_jina()


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_fetch_returns_markdown_and_metadata() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://r.jina.ai/https://example.com/article"
        return httpx.Response(
            200,
            text="# Example Article\n\nBody text",
            headers={"content-type": "text/markdown; charset=utf-8"},
            request=request,
        )

    async with _client(handler) as client:
        result = await FETCH_JINA.fetch("https://example.com/article", http_client=client)

    assert result["ok"] is True
    assert result["url"] == "https://example.com/article"
    assert result["reader_url"] == "https://r.jina.ai/https://example.com/article"
    assert result["markdown"] == "# Example Article\n\nBody text"
    assert result["metadata"]["title"] == "Example Article"
    assert result["metadata"]["status"] == 200
    assert result["metadata"]["content_type"] == "text/markdown; charset=utf-8"
    assert isinstance(result["metadata"]["fetched_at"], str)


@pytest.mark.asyncio
async def test_fetch_returns_structured_404_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found", request=request)

    async with _client(handler) as client:
        result = await FETCH_JINA.fetch("https://example.com/missing", http_client=client)

    assert result["ok"] is False
    assert result["markdown"] is None
    assert result["reason"] == "http_status"
    assert result["message"] == "Jina Reader returned HTTP 404"
    assert result["metadata"]["status"] == 404
    assert "suggest_fallback" not in result


@pytest.mark.asyncio
async def test_fetch_returns_structured_timeout_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with _client(handler) as client:
        result = await FETCH_JINA.fetch("https://example.com/slow", http_client=client)

    assert result["ok"] is False
    assert result["markdown"] is None
    assert result["reason"] == "timeout"
    assert result["message"] == "Jina Reader request timed out"
    assert result["metadata"]["status"] is None
    assert "suggest_fallback" not in result


@pytest.mark.asyncio
async def test_fetch_degrades_to_crawl4ai_on_anti_bot_refusal() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Access denied by anti-bot captcha", request=request)

    async with _client(handler) as client:
        result = await FETCH_JINA.fetch("https://www.zhihu.com/question/1", http_client=client)

    assert result["ok"] is False
    assert result["reason"] == "jina_refused"
    assert result["suggest_fallback"] == "fetch-crawl4ai"
    assert result["metadata"]["status"] == 403
