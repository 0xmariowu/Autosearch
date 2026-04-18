import httpx
import pytest
from pydantic import BaseModel

from autosearch.llm.providers.gemini import GeminiProvider


class _Out(BaseModel):
    answer: str


def _handler(captured: dict[str, object]) -> httpx.MockTransport:
    def respond(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": '{"answer":"ok"}'}]}}]},
        )

    return httpx.MockTransport(respond)


async def test_api_key_sent_in_header_not_url() -> None:
    captured: dict[str, object] = {}
    async with httpx.AsyncClient(transport=_handler(captured)) as client:
        provider = GeminiProvider(api_key="SECRET_SENTINEL", http_client=client)
        await provider.complete("hi", _Out)

    url = captured["url"]
    headers = captured["headers"]
    assert isinstance(url, str)
    assert isinstance(headers, dict)
    assert "SECRET_SENTINEL" not in url
    assert "key=" not in url
    assert headers.get("x-goog-api-key") == "SECRET_SENTINEL"


async def test_request_targets_generate_content_endpoint() -> None:
    captured: dict[str, object] = {}
    async with httpx.AsyncClient(transport=_handler(captured)) as client:
        provider = GeminiProvider(api_key="k", model="gemini-2.5-pro", http_client=client)
        await provider.complete("hi", _Out)

    url = captured["url"]
    assert isinstance(url, str)
    assert url.endswith("/v1beta/models/gemini-2.5-pro:generateContent")


def test_missing_api_key_raises() -> None:
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        GeminiProvider(api_key=None)
