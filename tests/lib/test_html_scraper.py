# Self-written for task F204
from __future__ import annotations

import httpx
import pytest

from autosearch.lib.html_scraper import HtmlFetchError, fetch_html


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetch_html_returns_response_text() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>ok</html>")

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        html_text = await fetch_html("https://example.com/page", http_client=client)

    assert html_text == "<html>ok</html>"


@pytest.mark.asyncio
async def test_fetch_html_sends_default_user_agent() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        return httpx.Response(200, text="<html>ok</html>")

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        await fetch_html("https://example.com/page", http_client=client)

    assert "Mozilla/5.0" in captured["user_agent"]
    assert "Chrome" in captured["user_agent"]


@pytest.mark.asyncio
async def test_fetch_html_merges_caller_headers() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        captured["x-test"] = request.headers.get("x-test", "")
        return httpx.Response(200, text="<html>ok</html>")

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        await fetch_html(
            "https://example.com/page",
            http_client=client,
            headers={"X-Test": "present"},
        )

    assert "Mozilla/5.0" in captured["user_agent"]
    assert captured["x-test"] == "present"


@pytest.mark.asyncio
async def test_fetch_html_raises_on_http_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden", request=request)

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        with pytest.raises(HtmlFetchError) as exc_info:
            await fetch_html("https://example.com/blocked", http_client=client)

    assert exc_info.value.status_code == 403
    assert exc_info.value.reason == "http_error"


@pytest.mark.asyncio
async def test_fetch_html_raises_on_transport_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        with pytest.raises(HtmlFetchError) as exc_info:
            await fetch_html("https://example.com/unreachable", http_client=client)

    assert exc_info.value.status_code is None
    assert "network down" in exc_info.value.reason
