from __future__ import annotations

import httpx
import pytest

from autosearch.channels.base import ChannelAuthError
from autosearch.lib.tikhub_client import (
    TikhubBudgetExhausted,
    TikhubClient,
    TikhubUpstreamError,
)


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _clear_tikhub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in (
        "AUTOSEARCH_PROXY_TOKEN",
        "AUTOSEARCH_PROXY_URL",
        "TIKHUB_API_KEY",
        "TIKHUB_BASE_URL",
    ):
        monkeypatch.delenv(env_var, raising=False)


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


@pytest.mark.asyncio
async def test_proxy_url_routes_to_proxy_with_proxy_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("AUTOSEARCH_PROXY_URL", "https://proxy.example.com")
    monkeypatch.setenv("AUTOSEARCH_PROXY_TOKEN", "proxy-abc")
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"data": {"ok": True}})

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        tikhub = TikhubClient(http_client=client)
        await tikhub.get("/api/v1/zhihu/web/fetch_article_search_v3", {"keyword": "llm"})

    url = captured["url"]
    assert isinstance(url, httpx.URL)
    assert url.host == "proxy.example.com"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers.get("authorization") == "Bearer proxy-abc"


def test_proxy_url_without_proxy_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOSEARCH_PROXY_URL", "https://proxy.example.com")
    monkeypatch.delenv("AUTOSEARCH_PROXY_TOKEN", raising=False)
    monkeypatch.delenv("TIKHUB_API_KEY", raising=False)

    with pytest.raises(
        ChannelAuthError,
        match="AUTOSEARCH_PROXY_TOKEN is required when AUTOSEARCH_PROXY_URL is set\\.",
    ):
        TikhubClient()


@pytest.mark.asyncio
async def test_tikhub_base_url_env_override_preserves_key_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("TIKHUB_BASE_URL", "https://custom.tikhub.io")
    monkeypatch.setenv("TIKHUB_API_KEY", "sk-123")

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"data": {"ok": True}})

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        tikhub = TikhubClient(http_client=client)
        await tikhub.get("/api/v1/zhihu/web/fetch_article_search_v3", {"keyword": "llm"})

    url = captured["url"]
    assert isinstance(url, httpx.URL)
    assert url.host == "custom.tikhub.io"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers.get("authorization") == "Bearer sk-123"


@pytest.mark.asyncio
async def test_proxy_mode_sanitizes_proxy_token_in_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOSEARCH_PROXY_URL", "https://proxy.example.com")
    monkeypatch.setenv("AUTOSEARCH_PROXY_TOKEN", "super-secret")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "detail": {
                    "headers": {"Authorization": "Bearer super-secret"},
                    "message": "forbidden",
                }
            },
        )

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        tikhub = TikhubClient(http_client=client)
        with pytest.raises(TikhubUpstreamError) as exc_info:
            await tikhub.get("/api/v1/zhihu/web/fetch_article_search_v3", {"keyword": "llm"})

    rendered = str(exc_info.value)
    assert "Bearer" not in rendered
    assert "super-secret" not in rendered


@pytest.mark.asyncio
async def test_explicit_kwargs_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("AUTOSEARCH_PROXY_URL", "https://proxy.example.com")
    monkeypatch.setenv("AUTOSEARCH_PROXY_TOKEN", "proxy-abc")

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"data": {"ok": True}})

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        tikhub = TikhubClient(
            api_key="kwarg-key",
            base_url="https://kwarg.example.com",
            http_client=client,
        )
        await tikhub.get("/api/v1/zhihu/web/fetch_article_search_v3", {"keyword": "llm"})

    url = captured["url"]
    assert isinstance(url, httpx.URL)
    assert url.host == "kwarg.example.com"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers.get("authorization") == "Bearer kwarg-key"


@pytest.mark.asyncio
async def test_base_url_trailing_slash_is_normalized() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"data": {"ok": True}})

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        tikhub = TikhubClient(
            api_key="test-key",
            base_url="https://proxy.example.com/",
            http_client=client,
        )
        await tikhub.get("/api/v1/zhihu/web/fetch_article_search_v3", {"keyword": "llm"})

    assert (
        captured["url"]
        == "https://proxy.example.com/api/v1/zhihu/web/fetch_article_search_v3?keyword=llm"
    )


@pytest.mark.asyncio
async def test_base_url_with_api_v1_prefix_does_not_double_prefix() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"data": {"ok": True}})

    async with httpx.AsyncClient(transport=_transport(handler)) as client:
        tikhub = TikhubClient(
            base_url="https://proxy.example.com/api/v1",
            proxy_token="proxy-abc",
            http_client=client,
        )
        await tikhub.get("/api/v1/zhihu/web/fetch_article_search_v3", {"keyword": "llm"})

    assert (
        captured["url"]
        == "https://proxy.example.com/api/v1/zhihu/web/fetch_article_search_v3?keyword=llm"
    )
