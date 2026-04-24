from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import cast

import httpx
import pytest

from autosearch.core.models import SubQuery
from autosearch.lib.tikhub_client import TikhubClient

TOKEN_LITERAL = "tikhub-secret-token-for-tiktok-test"


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "tiktok"
        / "methods"
        / "via_tikhub.py"
    )
    spec = importlib.util.spec_from_file_location("test_tiktok_via_tikhub", module_path)
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
    return SubQuery(text="wireless earbuds", rationale="Need TikTok creator coverage")


def _video_item(
    *,
    aweme_id: int | None,
    desc: str,
    unique_id: str | None,
    nickname: str | None,
    share_url: str | None = None,
) -> dict[str, object]:
    author: dict[str, object] = {}
    if unique_id is not None:
        author["unique_id"] = unique_id
    if nickname is not None:
        author["nickname"] = nickname

    aweme_info: dict[str, object] = {"desc": desc, "author": author}
    if aweme_id is not None:
        aweme_info["aweme_id"] = aweme_id
    if share_url is not None:
        aweme_info["share_url"] = share_url

    return {"aweme_info": aweme_info}


@pytest.mark.asyncio
async def test_search_maps_items_to_evidence() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": [
                    _video_item(
                        aweme_id=1234,
                        desc="  First launch clip with emoji 🚀  ",
                        unique_id="creator_one",
                        nickname="Creator One",
                        share_url="https://www.tiktok.com/@creator_one/video/1234?lang=en",
                    ),
                    _video_item(
                        aweme_id=5678,
                        desc="Second creator demo clip.",
                        unique_id="creator_two",
                        nickname=None,
                        share_url="https://www.tiktok.com/@creator_two/video/5678?lang=en",
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
                "keyword": "wireless earbuds",
                "offset": 0,
                "count": 20,
                "sort_type": 0,
                "publish_time": 0,
            },
        )
    ]
    assert len(results) == 2

    first = results[0]
    assert first.url == "https://www.tiktok.com/@creator_one/video/1234?lang=en"
    assert first.title == "@Creator One"
    assert first.snippet == "First launch clip with emoji 🚀"
    assert first.source_channel == "tiktok:tikhub"
    assert first.fetched_at.tzinfo is MODULE.UTC

    second = results[1]
    assert second.url == "https://www.tiktok.com/@creator_two/video/5678?lang=en"
    assert second.title == "@creator_two"
    assert second.snippet == "Second creator demo clip."
    assert second.source_channel == "tiktok:tikhub"


@pytest.mark.asyncio
async def test_search_skips_items_without_required_fields() -> None:
    client = _FakeTikhubClient({"data": {"data": [{}, {"aweme_info": "bad-shape"}]}})

    results = await search(_query(), client=cast(TikhubClient, client))

    assert results == []


@pytest.mark.asyncio
async def test_search_uses_fallback_url_when_share_url_missing() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": [
                    _video_item(
                        aweme_id=4321,
                        desc="Fallback URL example.",
                        unique_id="fallback_creator",
                        nickname="Fallback Creator",
                    )
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].url == "https://www.tiktok.com/@fallback_creator/video/4321"


@pytest.mark.asyncio
async def test_search_skips_item_with_no_usable_id() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": [
                    _video_item(
                        aweme_id=None,
                        desc="No usable id means no canonical URL.",
                        unique_id="broken_creator",
                        nickname="Broken Creator",
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
    assert logger.events[0][0] == "tiktok_tikhub_search_failed"
    reason = str(logger.events[0][1]["reason"])
    assert SEARCH_PATH in reason
    assert "Bearer" not in reason
    assert TOKEN_LITERAL not in reason


@pytest.mark.asyncio
async def test_search_truncates_long_text_to_snippet() -> None:
    long_desc = ("word " * 59) + "splitpoint continues after the limit"
    client = _FakeTikhubClient(
        {
            "data": {
                "data": [
                    _video_item(
                        aweme_id=9999,
                        desc=long_desc,
                        unique_id="long_creator",
                        nickname="Long Creator",
                        share_url="https://www.tiktok.com/@long_creator/video/9999",
                    )
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].snippet == f"{('word ' * 59).strip()}…"
    assert results[0].content == long_desc
