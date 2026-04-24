from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import cast

import httpx
import pytest

from autosearch.core.models import SubQuery
from autosearch.lib.tikhub_client import TikhubClient

TOKEN_LITERAL = "tikhub-secret-token-for-kuaishou-test"


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "kuaishou"
        / "methods"
        / "via_tikhub.py"
    )
    spec = importlib.util.spec_from_file_location("test_kuaishou_via_tikhub", module_path)
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


class _FailingHTTPClient:
    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, object],
    ) -> httpx.Response:
        request = httpx.Request("GET", url, headers=headers, params=params)
        authorization = headers.get("Authorization", "")
        return httpx.Response(
            403,
            json={
                "detail": {
                    "message": "forbidden",
                    "headers": {"Authorization": authorization},
                    "nested": {"explanation": f"received {authorization}"},
                }
            },
            request=request,
        )


class _FailingTikhubClient(TikhubClient):
    def __init__(self, api_key: str) -> None:
        super().__init__(
            api_key=api_key,
            http_client=cast(httpx.AsyncClient, _FailingHTTPClient()),
        )


def _query() -> SubQuery:
    return SubQuery(text="国货咖啡机", rationale="Need Kuaishou short-video coverage")


def _feed_item(
    *,
    item_type: int,
    photo_id: str | None,
    caption: str,
    user_name: str | None,
    extra_feed: dict[str, object] | None = None,
) -> dict[str, object]:
    feed: dict[str, object] = {"caption": caption, "photoId": None}
    if user_name is not None:
        feed["user_name"] = user_name
    if photo_id is not None:
        feed["photo_id"] = photo_id
    if extra_feed is not None:
        feed.update(extra_feed)
    return {"itemType": item_type, "feed": feed}


@pytest.mark.asyncio
async def test_search_maps_items_to_evidence() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "mixFeeds": [
                    _feed_item(
                        item_type=1,
                        photo_id="3xk9abcd",
                        caption="  第一条测评短视频  ",
                        user_name="快手作者A",
                    ),
                    _feed_item(
                        item_type=1,
                        photo_id="4mn0wxyz",
                        caption="第二条演示视频。",
                        user_name=None,
                    ),
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert client.calls == [
        (
            SEARCH_PATH,
            {
                "keyword": "国货咖啡机",
                "sort_type": "all",
                "publish_time": "all",
                "duration": "all",
                "search_scope": "all",
            },
        )
    ]
    assert len(results) == 2

    first = results[0]
    assert first.url == "https://www.kuaishou.com/short-video/3xk9abcd"
    assert first.title == "@快手作者A"
    assert first.snippet == "第一条测评短视频"
    assert first.source_channel == "kuaishou:tikhub"
    assert first.fetched_at.tzinfo is MODULE.UTC

    second = results[1]
    assert second.url == "https://www.kuaishou.com/short-video/4mn0wxyz"
    assert second.title == "Kuaishou video"
    assert second.snippet == "第二条演示视频。"
    assert second.source_channel == "kuaishou:tikhub"


@pytest.mark.asyncio
async def test_search_skips_items_without_required_fields() -> None:
    client = _FakeTikhubClient({"data": {"mixFeeds": [{"itemType": 100}, {"feed": "bad-shape"}]}})

    results = await search(_query(), client=cast(TikhubClient, client))

    assert results == []


@pytest.mark.asyncio
async def test_search_skips_item_with_no_usable_id() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "mixFeeds": [
                    _feed_item(
                        item_type=1,
                        photo_id=None,
                        caption="Only camelCase id should not be used.",
                        user_name="Broken Feed",
                        extra_feed={"photoId": "camel-only"},
                    )
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert results == []


@pytest.mark.asyncio
async def test_search_returns_empty_on_tikhub_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    # Bug 1 (fix-plan): typed exception now propagates instead of [].
    from autosearch.channels.base import (
        ChannelAuthError,
        PermanentError,
        RateLimited,
        TransientError,
    )

    with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
        await search(_query(), client=_FailingTikhubClient(TOKEN_LITERAL))

    assert logger.events
    assert logger.events[0][0] == "kuaishou_tikhub_search_failed"
    reason = str(logger.events[0][1]["reason"])
    assert SEARCH_PATH in reason
    assert "Bearer" not in reason
    assert TOKEN_LITERAL not in reason


@pytest.mark.asyncio
async def test_search_truncates_long_text_to_snippet() -> None:
    long_caption = ("word " * 59) + "splitpoint continues after the limit"
    client = _FakeTikhubClient(
        {
            "data": {
                "mixFeeds": [
                    _feed_item(
                        item_type=1,
                        photo_id="long-caption-id",
                        caption=long_caption,
                        user_name="长文案作者",
                    )
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].snippet == f"{('word ' * 59).strip()}…"
    assert results[0].content == long_caption


@pytest.mark.asyncio
async def test_search_skips_non_video_itemtypes() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "mixFeeds": [
                    {"itemType": 301, "title": "search header"},
                    _feed_item(
                        item_type=102,
                        photo_id=None,
                        caption="Ad card without a real photo id.",
                        user_name="广告账号",
                    ),
                    _feed_item(
                        item_type=1,
                        photo_id="real-video-id",
                        caption="真正的视频内容。",
                        user_name="真实作者",
                    ),
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].url == "https://www.kuaishou.com/short-video/real-video-id"
    assert results[0].title == "@真实作者"
