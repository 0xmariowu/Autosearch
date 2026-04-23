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
    """Single-step fake: get() returns search results directly (no sign step)."""

    def __init__(self, search_payload: dict[str, object]) -> None:
        self.search_payload = search_payload
        self.get_calls: list[tuple[str, dict[str, object]]] = []

    async def get(
        self,
        path: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        self.get_calls.append((path, params))
        return self.search_payload


class _FailingTikhubClient:
    async def get(
        self,
        path: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        raise TikhubError(f"request failed for {path}")


def _query() -> SubQuery:
    return SubQuery(text="防晒", rationale="Need Xiaohongshu product review coverage")


def _note_item(
    note_id: str,
    display_title: str,
    desc: str = "",
    xsec_token: str = "",
) -> dict[str, object]:
    return {
        "id": note_id,
        "xsecToken": xsec_token,
        "noteCard": {
            "displayTitle": display_title,
            "desc": desc,
            "user": {"nickname": "Test User"},
        },
    }


def _search_payload(items: list[dict]) -> dict[str, object]:
    return {"data": {"data": {"items": items}}}


@pytest.mark.asyncio
async def test_search_maps_xhs_items_to_evidence() -> None:
    client = _FakeTikhubClient(
        _search_payload(
            [
                _note_item(
                    "note-abc",
                    "护肤 &amp; 防晒推荐 ",
                    desc="适合夏天通勤使用，质地很轻薄。",
                    xsec_token="token-abc",
                ),
                _note_item(
                    "note-def",
                    "旅行清单",
                    desc="出发前一定要带上防晒和补水喷雾。",
                    xsec_token="token-def",
                ),
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    # Direct GET to SEARCH_PATH — no sign step
    assert len(client.get_calls) == 1
    assert client.get_calls[0][0] == SEARCH_PATH
    assert client.get_calls[0][1]["keyword"] == "防晒"

    assert len(results) == 2

    first = results[0]
    assert "note-abc" in first.url
    assert "token-abc" in first.url
    assert first.title == "护肤 & 防晒推荐"
    assert first.snippet == "适合夏天通勤使用，质地很轻薄。"
    assert first.source_channel == "xiaohongshu:tikhub"

    second = results[1]
    assert "note-def" in second.url
    assert second.title == "旅行清单"
    assert second.snippet == "出发前一定要带上防晒和补水喷雾。"
    assert second.source_channel == "xiaohongshu:tikhub"


@pytest.mark.asyncio
async def test_search_uses_id_without_xsec_when_token_missing() -> None:
    client = _FakeTikhubClient(
        _search_payload([_note_item("note-fallback", "好物分享", desc="没有 xsec token。")])
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert "note-fallback" in results[0].url


@pytest.mark.asyncio
async def test_search_skips_item_without_id() -> None:
    client = _FakeTikhubClient(
        _search_payload(
            [
                {
                    "noteCard": {"displayTitle": "No ID note", "desc": "Should be skipped."},
                }
            ]
        )
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


@pytest.mark.asyncio
async def test_search_truncates_desc_to_snippet_on_word_boundary() -> None:
    long_desc = ("word " * 59) + "splitpoint continues after the limit"
    client = _FakeTikhubClient(
        _search_payload([_note_item("note-long", "Long note", desc=long_desc, xsec_token="tok")])
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].snippet == f"{('word ' * 59).strip()}…"
    assert results[0].content == long_desc
