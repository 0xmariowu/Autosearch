from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import cast

import pytest

from autosearch.core.models import SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "twitter"
        / "methods"
        / "via_tikhub.py"
    )
    spec = importlib.util.spec_from_file_location("test_twitter_via_tikhub", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
SEARCH_PATH = MODULE.SEARCH_PATH
search = MODULE.search


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


class _FakeTikhubClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def get(self, path: str, params: dict[str, object], **_: object) -> dict[str, object]:
        self.calls.append((path, params))
        return self.payload


class _FailingTikhubClient:
    async def get(self, path: str, params: dict[str, object], **_: object) -> dict[str, object]:
        raise TikhubError(f"request failed for {path} with {params!r}")


def _query() -> SubQuery:
    return SubQuery(text="OpenAI launch", rationale="Need Twitter launch coverage")


def _flat_tweet(
    tweet_id: str,
    screen_name: str,
    text: str,
) -> dict[str, object]:
    """Build a tweet in the current flat timeline format."""
    return {
        "tweet_id": tweet_id,
        "screen_name": screen_name,
        "text": text,
        "created_at": "Thu Apr 23 10:00:00 +0000 2026",
        "entities": {},
    }


def _timeline_payload(tweets: list[dict[str, object]]) -> dict[str, object]:
    """Wrap tweets in the current flat data.timeline structure."""
    return {"data": {"timeline": tweets, "next_cursor": "", "prev_cursor": ""}}


@pytest.mark.asyncio
async def test_search_extracts_tweets_from_flat_timeline() -> None:
    client = _FakeTikhubClient(
        _timeline_payload(
            [
                _flat_tweet("1234567890", "openai", "OpenAI ships a new API update."),
                _flat_tweet("9876543210", "sama", "Second launch note with &amp; entity cleanup."),
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert client.calls == [
        (SEARCH_PATH, {"keyword": "OpenAI launch", "search_type": "Latest"}),
    ]
    assert len(results) == 2

    first = results[0]
    assert first.url == "https://x.com/openai/status/1234567890"
    assert first.title == "OpenAI ships a new API update."
    assert first.snippet == "OpenAI ships a new API update."
    assert first.content == "OpenAI ships a new API update."
    assert first.source_channel == "twitter:openai"

    second = results[1]
    assert second.url == "https://x.com/sama/status/9876543210"
    assert second.title == "Second launch note with & entity cleanup."
    assert second.source_channel == "twitter:sama"


@pytest.mark.asyncio
async def test_search_skips_tweet_without_id_or_screen_name() -> None:
    client = _FakeTikhubClient(
        _timeline_payload(
            [
                {"screen_name": "openai", "text": "Missing tweet_id."},
                {"tweet_id": "123", "text": "Missing screen_name."},
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert results == []


@pytest.mark.asyncio
async def test_search_source_channel_includes_screen_name() -> None:
    client = _FakeTikhubClient(
        _timeline_payload([_flat_tweet("1234567890", "elonmusk", "Launch timing update.")])
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].source_channel == "twitter:elonmusk"


@pytest.mark.asyncio
async def test_search_returns_empty_on_empty_timeline() -> None:
    client = _FakeTikhubClient({"data": {"timeline": []}})

    results = await search(_query(), client=cast(TikhubClient, client))

    assert results == []


@pytest.mark.asyncio
async def test_search_returns_empty_on_tikhub_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    # Bug 1 (fix-plan): TikhubError now propagates as a typed channel
    # error so the MCP boundary can surface auth_failed / rate_limited /
    # channel_error instead of an indistinguishable empty result.
    from autosearch.channels.base import TransientError

    with pytest.raises(TransientError):
        await search(_query(), client=cast(TikhubClient, _FailingTikhubClient()))

    assert logger.events
    assert logger.events[0][0] == "twitter_tikhub_search_failed"
    assert SEARCH_PATH in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_handles_unexpected_payload_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autosearch.channels.base import PermanentError

    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)
    client = _FakeTikhubClient({"data": {"unexpected": "shape"}})

    with pytest.raises(PermanentError):
        await search(_query(), client=cast(TikhubClient, client))

    assert logger.events == []
