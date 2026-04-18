# Self-written, plan autosearch-0418-channels-and-skills.md § F005
import json
from pathlib import Path

import httpx
import pytest

import autosearch.channels.youtube as youtube_module
from autosearch.channels.youtube import YouTubeChannel
from autosearch.core.models import Evidence, SubQuery

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _fixture_json(name: str) -> dict[str, object]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _patch_async_client(
    monkeypatch: pytest.MonkeyPatch,
    transport: httpx.MockTransport,
) -> None:
    original_async_client = httpx.AsyncClient

    def factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return original_async_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr(youtube_module.httpx, "AsyncClient", factory)


def _transport(
    payload: object | None = None,
    *,
    status_code: int = 200,
    captured: dict[str, object] | None = None,
) -> httpx.MockTransport:
    def respond(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured["url"] = str(request.url)
            captured["params"] = dict(request.url.params)
            captured["headers"] = dict(request.headers)
        return httpx.Response(status_code, json=payload, request=request)

    return httpx.MockTransport(respond)


@pytest.mark.asyncio
async def test_search_maps_items_to_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _fixture_json("youtube_response.json")
    _patch_async_client(monkeypatch, _transport(payload))

    results = await YouTubeChannel(api_key="test-key").search(
        SubQuery(text="bm25 tutorial", rationale="Need introductory videos")
    )

    assert len(results) == 3
    assert all(isinstance(item, Evidence) for item in results)
    assert results[0].url == "https://www.youtube.com/watch?v=video-001"
    assert results[0].title == "BM25 Tutorial for Search Engineers"
    assert results[0].snippet == "A practical introduction to BM25 ranking for search applications."
    assert all(item.source_channel == "youtube" for item in results)
    assert all(item.score == 0.0 for item in results)


@pytest.mark.asyncio
async def test_search_without_api_key_returns_empty_and_warns_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setattr(youtube_module, "LOGGER", logger)
    channel = YouTubeChannel(api_key=None)

    first = await channel.search(SubQuery(text="bm25 tutorial", rationale="Need videos"))
    second = await channel.search(SubQuery(text="dense retrieval", rationale="Need videos"))

    assert first == []
    assert second == []
    assert logger.events == [
        (
            "youtube_search_skipped",
            {"channel": "youtube", "reason": "no_api_key"},
        )
    ]


@pytest.mark.asyncio
async def test_api_key_in_header_not_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    _patch_async_client(monkeypatch, _transport({"items": []}, captured=captured))

    await YouTubeChannel(api_key="SECRET_SENTINEL").search(
        SubQuery(text="bm25 tutorial", rationale="Need videos")
    )

    url = captured["url"]
    headers = captured["headers"]
    assert isinstance(url, str)
    assert isinstance(headers, dict)
    assert "SECRET_SENTINEL" not in url
    assert "key=" not in url
    assert headers.get("x-goog-api-key") == "SECRET_SENTINEL"


@pytest.mark.asyncio
async def test_api_key_value_not_in_logs_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    monkeypatch.setattr(youtube_module, "LOGGER", logger)
    _patch_async_client(monkeypatch, _transport({"error": "denied"}, status_code=401))

    results = await YouTubeChannel(api_key="SECRET_SENTINEL").search(
        SubQuery(text="bm25 tutorial", rationale="Need videos")
    )

    assert results == []
    assert logger.events == [
        (
            "youtube_search_failed",
            {"channel": "youtube", "reason": "auth_failed"},
        )
    ]
    assert logger.events
    assert "SECRET_SENTINEL" not in json.dumps(logger.events)


@pytest.mark.asyncio
async def test_html_entities_unescaped_in_title_and_snippet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "items": [
            {
                "id": {"videoId": "video-entities"},
                "snippet": {
                    "title": "Don&#39;t Panic &amp; Rank Better",
                    "description": "Use BM25 &amp; TF-IDF, don&#39;t overfit.",
                },
            }
        ]
    }
    _patch_async_client(monkeypatch, _transport(payload))

    results = await YouTubeChannel(api_key="test-key").search(
        SubQuery(text="bm25 entities", rationale="Need unescape coverage")
    )

    assert results[0].title == "Don't Panic & Rank Better"
    assert results[0].snippet == "Use BM25 & TF-IDF, don't overfit."


@pytest.mark.asyncio
async def test_snippet_truncated_to_500_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "items": [
            {
                "id": {"videoId": "video-long"},
                "snippet": {
                    "title": "Long description video",
                    "description": "a" * 750,
                },
            }
        ]
    }
    _patch_async_client(monkeypatch, _transport(payload))

    results = await YouTubeChannel(api_key="test-key").search(
        SubQuery(text="long description", rationale="Need truncation coverage")
    )

    assert results[0].snippet is not None
    assert len(results[0].snippet) == 500
    assert results[0].snippet == "a" * 500


@pytest.mark.asyncio
async def test_network_error_returns_empty_and_warns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()

    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    _patch_async_client(monkeypatch, httpx.MockTransport(respond))
    monkeypatch.setattr(youtube_module, "LOGGER", logger)

    results = await YouTubeChannel(api_key="test-key").search(
        SubQuery(text="bm25 tutorial", rationale="Need videos")
    )

    assert results == []
    assert logger.events == [
        (
            "youtube_search_failed",
            {"channel": "youtube", "reason": "boom"},
        )
    ]


@pytest.mark.asyncio
async def test_empty_items_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    _patch_async_client(monkeypatch, _transport({"items": []}))
    monkeypatch.setattr(youtube_module, "LOGGER", logger)

    results = await YouTubeChannel(api_key="test-key").search(
        SubQuery(text="no videos", rationale="Need empty search coverage")
    )

    assert results == []
    assert logger.events == []
