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
        / "xiaohongshu"
        / "methods"
        / "via_tikhub.py"
    )
    spec = importlib.util.spec_from_file_location("test_xiaohongshu_via_tikhub", module_path)
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
    return SubQuery(text="防晒", rationale="Need Xiaohongshu product review coverage")


@pytest.mark.asyncio
async def test_search_maps_xhs_items_to_evidence() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "items": [
                    {
                        "id": "note-abc",
                        "title": "护肤 &amp; 防晒推荐 ",
                        "desc": "适合夏天通勤使用，质地很轻薄。",
                        "share_info": {"link": "https://www.xiaohongshu.com/explore/note-abc"},
                    },
                    {
                        "id": "note-def",
                        "title": "旅行清单",
                        "desc": "出发前一定要带上防晒和补水喷雾。",
                        "share_info": {"link": "https://www.xiaohongshu.com/explore/note-def"},
                    },
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert client.calls == [(SEARCH_PATH, {"keyword": "防晒"})]
    assert len(results) == 2

    first = results[0]
    assert first.url == "https://www.xiaohongshu.com/explore/note-abc"
    assert first.title == "护肤 & 防晒推荐"
    assert first.snippet == "适合夏天通勤使用，质地很轻薄。"
    assert first.content == "适合夏天通勤使用，质地很轻薄。"
    assert first.source_channel == "xiaohongshu:tikhub"

    second = results[1]
    assert second.url == "https://www.xiaohongshu.com/explore/note-def"
    assert second.title == "旅行清单"
    assert second.snippet == "出发前一定要带上防晒和补水喷雾。"
    assert second.source_channel == "xiaohongshu:tikhub"


@pytest.mark.asyncio
async def test_search_uses_id_fallback_when_share_info_missing() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "items": [
                    {
                        "id": "note-fallback",
                        "title": "好物分享",
                        "desc": "没有 share link 时使用 note id。",
                    }
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].url == "https://www.xiaohongshu.com/explore/note-fallback"


@pytest.mark.asyncio
async def test_search_skips_item_without_id_or_share_link() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "items": [
                    {
                        "title": "Broken item",
                        "desc": "This should be skipped.",
                        "share_info": {},
                    }
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

    results = await search(_query(), client=cast(TikhubClient, _FailingTikhubClient()))

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "xiaohongshu_tikhub_search_failed"
    assert SEARCH_PATH in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_truncates_desc_to_snippet_on_word_boundary() -> None:
    long_desc = ("word " * 59) + "splitpoint continues after the limit"
    client = _FakeTikhubClient(
        {
            "data": {
                "items": [
                    {
                        "id": "note-long",
                        "title": "Long note",
                        "desc": long_desc,
                    }
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].snippet == f"{('word ' * 59).strip()}…"
    assert results[0].content == long_desc
