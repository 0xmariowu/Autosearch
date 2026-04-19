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

    async def get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        self.calls.append((path, params))
        return self.payload


class _FailingTikhubClient:
    async def get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        raise TikhubError(f"request failed for {path} with {params!r}")


def _query() -> SubQuery:
    return SubQuery(text="OpenAI launch", rationale="Need Twitter launch coverage")


def _tweet_result(
    *, rest_id: str | None, screen_name: str | None, full_text: str
) -> dict[str, object]:
    result: dict[str, object] = {
        "legacy": {"full_text": full_text},
        "core": {
            "user_results": {
                "result": {
                    "legacy": {},
                }
            }
        },
    }
    if rest_id is not None:
        result["rest_id"] = rest_id
    if screen_name is not None:
        result["core"]["user_results"]["result"]["legacy"]["screen_name"] = screen_name
    return result


def _timeline_payload(results: list[dict[str, object]]) -> dict[str, object]:
    return {
        "data": {
            "data": {
                "search_by_raw_query": {
                    "search_timeline": {
                        "timeline": {
                            "instructions": [
                                {
                                    "type": "TimelineAddEntries",
                                    "entries": [
                                        {
                                            "content": {
                                                "itemContent": {
                                                    "tweet_results": {
                                                        "result": result,
                                                    }
                                                }
                                            }
                                        }
                                        for result in results
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
        }
    }


@pytest.mark.asyncio
async def test_search_extracts_tweets_from_nested_structure() -> None:
    client = _FakeTikhubClient(
        _timeline_payload(
            [
                _tweet_result(
                    rest_id="1234567890",
                    screen_name="openai",
                    full_text="OpenAI ships a new API update.",
                ),
                _tweet_result(
                    rest_id="9876543210",
                    screen_name="sama",
                    full_text="Second launch note with &amp; entity cleanup.",
                ),
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert client.calls == [
        (
            SEARCH_PATH,
            {"keyword": "OpenAI launch", "search_type": "Top"},
        )
    ]
    assert len(results) == 2

    first = results[0]
    assert first.url == "https://twitter.com/openai/status/1234567890"
    assert first.title == "OpenAI ships a new API update."
    assert first.snippet == "OpenAI ships a new API update."
    assert first.content == "OpenAI ships a new API update."
    assert first.source_channel == "twitter:openai"

    second = results[1]
    assert second.url == "https://twitter.com/sama/status/9876543210"
    assert second.title == "Second launch note with & entity cleanup."
    assert second.snippet == "Second launch note with & entity cleanup."


@pytest.mark.asyncio
async def test_search_skips_tweet_without_rest_id_or_screen_name() -> None:
    client = _FakeTikhubClient(
        _timeline_payload(
            [
                _tweet_result(rest_id=None, screen_name="openai", full_text="Missing rest id."),
                _tweet_result(rest_id="123", screen_name=None, full_text="Missing screen name."),
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert results == []


@pytest.mark.asyncio
async def test_search_source_channel_includes_screen_name() -> None:
    client = _FakeTikhubClient(
        _timeline_payload(
            [
                _tweet_result(
                    rest_id="1234567890",
                    screen_name="elonmusk",
                    full_text="Launch timing update.",
                )
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].source_channel == "twitter:elonmusk"


@pytest.mark.asyncio
async def test_search_returns_empty_on_empty_timeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)
    client = _FakeTikhubClient(
        {
            "data": {
                "data": {
                    "search_by_raw_query": {"search_timeline": {"timeline": {"instructions": []}}}
                }
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert results == []
    assert logger.events == []


@pytest.mark.asyncio
async def test_search_returns_empty_on_tikhub_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    results = await search(_query(), client=cast(TikhubClient, _FailingTikhubClient()))

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "twitter_tikhub_search_failed"
    assert SEARCH_PATH in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_handles_unexpected_payload_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)
    client = _FakeTikhubClient({"data": {"unexpected": "shape"}})

    results = await search(_query(), client=cast(TikhubClient, client))

    assert results == []
    assert logger.events == []
