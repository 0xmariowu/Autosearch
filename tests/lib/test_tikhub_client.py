from __future__ import annotations

import httpx
import pytest

from autosearch.lib.tikhub_client import (
    TikhubBudgetExhausted,
    TikhubClient,
    TikhubUpstreamError,
)


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_get_success_returns_parsed_json() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"data": {"ok": True}})

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        tikhub = TikhubClient(api_key="test-key", http_client=client)
        payload = await tikhub.get("/api/v1/zhihu/web/fetch_article_search_v3", {"keyword": "llm"})

    assert payload == {"data": {"ok": True}}
    assert (
        captured["url"]
        == "https://api.tikhub.io/api/v1/zhihu/web/fetch_article_search_v3?keyword=llm"
    )
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers.get("authorization") == "Bearer test-key"


@pytest.mark.asyncio
async def test_get_402_raises_budget_exhausted() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"detail": {"message": "balance exhausted"}})

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        tikhub = TikhubClient(api_key="test-key", http_client=client)
        with pytest.raises(TikhubBudgetExhausted, match="status=402"):
            await tikhub.get("/api/v1/tikhub/user/get_user_daily_usage", {})


@pytest.mark.asyncio
async def test_get_403_sanitizes_echoed_authorization_header() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "detail": {
                    "message": "forbidden",
                    "headers": {
                        "Authorization": "Bearer secret-token",
                        "X-Test": "1",
                    },
                    "nested": {
                        "auth_token": "secret-token",
                        "explanation": "received Bearer secret-token",
                    },
                }
            },
        )

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        tikhub = TikhubClient(api_key="test-key", http_client=client)
        with pytest.raises(TikhubUpstreamError) as exc_info:
            await tikhub.get("/api/v1/zhihu/web/fetch_article_search_v3", {"keyword": "llm"})

    rendered = str(exc_info.value)
    assert "Bearer" not in rendered
    assert "secret-token" not in rendered


def test_missing_api_key_env_var_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)

    with pytest.raises(ValueError, match="TIKHUB_API_KEY"):
        TikhubClient(api_key=None)
