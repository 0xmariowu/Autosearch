# Self-written, plan autosearch-0418-channels-and-skills.md § F005
import json
from pathlib import Path

import httpx
import pytest

import autosearch.channels.hackernews as hackernews_module
from autosearch.channels.hackernews import HackerNewsChannel
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

    monkeypatch.setattr(hackernews_module.httpx, "AsyncClient", factory)


def _transport(
    payload: object,
    *,
    captured: dict[str, object] | None = None,
) -> httpx.MockTransport:
    def respond(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured["url"] = str(request.url)
            captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=payload, request=request)

    return httpx.MockTransport(respond)


@pytest.mark.asyncio
async def test_search_maps_story_hit_to_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    payload = _fixture_json("hackernews_response.json")
    _patch_async_client(monkeypatch, _transport(payload, captured=captured))

    results = await HackerNewsChannel().search(
        SubQuery(text="Rust vs Go", rationale="Need HN discussion")
    )

    assert len(results) == 3
    assert all(isinstance(item, Evidence) for item in results)
    assert (
        captured["url"]
        == "https://hn.algolia.com/api/v1/search?query=Rust+vs+Go&hitsPerPage=10&tags=%28story%2Ccomment%29"
    )
    assert captured["params"] == {
        "query": "Rust vs Go",
        "hitsPerPage": "10",
        "tags": "(story,comment)",
    }
    assert results[0].url == "https://example.com/rust-vs-go"
    assert results[0].title == "Rust vs Go in 2026"
    assert results[0].source_channel == "hackernews"
    assert results[0].score == 0.0


@pytest.mark.asyncio
async def test_search_maps_comment_hit_uses_internal_item_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _fixture_json("hackernews_response.json")
    _patch_async_client(monkeypatch, _transport(payload))

    results = await HackerNewsChannel().search(
        SubQuery(text="Rust vs Go", rationale="Need HN discussion")
    )

    comment_text = str((payload["hits"])[2]["comment_text"])
    assert results[2].url == "https://news.ycombinator.com/item?id=1003"
    assert results[2].title == f"{comment_text[:80]}..."


@pytest.mark.asyncio
async def test_search_story_with_null_external_url_falls_back_to_hn_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _fixture_json("hackernews_response.json")
    _patch_async_client(monkeypatch, _transport(payload))

    results = await HackerNewsChannel().search(
        SubQuery(text="build cache", rationale="Need Ask HN coverage")
    )

    assert results[1].url == "https://news.ycombinator.com/item?id=1002"
    assert results[1].title == "Ask HN: Show me your build cache tricks"


@pytest.mark.asyncio
async def test_search_strips_html_from_snippet(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "hits": [
            {
                "objectID": "9999",
                "title": None,
                "url": None,
                "comment_text": '<p>Use the <a href="https://example.com">link</a> text.</p>',
            }
        ]
    }
    _patch_async_client(monkeypatch, _transport(payload))

    results = await HackerNewsChannel().search(
        SubQuery(text="html snippet", rationale="Need sanitization coverage")
    )

    assert results[0].snippet == "Use the link text."
    assert "<" not in results[0].snippet
    assert ">" not in results[0].snippet


@pytest.mark.asyncio
async def test_search_empty_hits_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    _patch_async_client(monkeypatch, _transport({"hits": []}))
    monkeypatch.setattr(hackernews_module, "LOGGER", logger)

    results = await HackerNewsChannel().search(
        SubQuery(text="no hits", rationale="Need empty search coverage")
    )

    assert results == []
    assert logger.events == []


@pytest.mark.asyncio
async def test_search_network_error_returns_empty_and_warns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()

    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    _patch_async_client(monkeypatch, httpx.MockTransport(respond))
    monkeypatch.setattr(hackernews_module, "LOGGER", logger)

    results = await HackerNewsChannel().search(
        SubQuery(text="Rust vs Go", rationale="Need HN discussion")
    )

    assert results == []
    assert logger.events == [
        (
            "hackernews_search_failed",
            {"channel": "hackernews", "reason": "boom"},
        )
    ]


@pytest.mark.asyncio
async def test_snippet_truncated_to_500_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    story_text = "a" * 750
    payload = {
        "hits": [
            {
                "objectID": "5000",
                "title": "Long story",
                "url": "https://example.com/long-story",
                "story_text": story_text,
            }
        ]
    }
    _patch_async_client(monkeypatch, _transport(payload))

    results = await HackerNewsChannel().search(
        SubQuery(text="Long story", rationale="Need truncation coverage")
    )

    assert results[0].snippet is not None
    assert len(results[0].snippet) == 500
    assert results[0].snippet == story_text[:500]
