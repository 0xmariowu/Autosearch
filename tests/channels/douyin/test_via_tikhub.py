# Self-written for task F205
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
        / "douyin"
        / "methods"
        / "via_tikhub.py"
    )
    spec = importlib.util.spec_from_file_location("test_douyin_via_tikhub", module_path)
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

    async def post(self, path: str, body: dict[str, object]) -> dict[str, object]:
        self.calls.append((path, body))
        return self.payload


class _FailingTikhubClient:
    async def get(self, path: str, params: dict[str, object], **_: object) -> dict[str, object]:
        raise TikhubError(f"request failed for {path} with {params!r}")

    async def post(self, path: str, body: dict[str, object]) -> dict[str, object]:
        raise TikhubError(f"request failed for {path} with {body!r}")


def _query() -> SubQuery:
    return SubQuery(text="科技评测", rationale="Need Douyin short-video review coverage")


def _video_entry(
    *,
    aweme_id: str,
    desc: str,
    nickname: str | None,
    share_url: str | None = None,
) -> dict[str, object]:
    author: dict[str, object] = {"sec_uid": "MS4w..."}
    if nickname is not None:
        author["nickname"] = nickname

    aweme_info: dict[str, object] = {
        "aweme_id": aweme_id,
        "desc": desc,
        "author": author,
        "statistics": {"digg_count": 1200, "comment_count": 45},
        "video": {"cover": {"url_list": ["https://example.com/cover.jpg"]}},
    }
    if share_url is not None:
        aweme_info["share_url"] = share_url

    return {"type": 1, "aweme_info": aweme_info}


@pytest.mark.asyncio
async def test_search_maps_douyin_videos_to_evidence() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": [
                    _video_entry(
                        aweme_id="7234567890",
                        desc="First &amp; latest phone teardown clip.",
                        nickname="Tech Reviewer",
                        share_url="https://v.douyin.com/abc123/",
                    ),
                    _video_entry(
                        aweme_id="7234567891",
                        desc="Second comparison video for a new gadget.",
                        nickname="Device Lab",
                        share_url="https://v.douyin.com/def456/",
                    ),
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert client.calls == [(SEARCH_PATH, {"keyword": "科技评测", "cursor": 0, "sort_type": "0"})]
    assert len(results) == 2

    first = results[0]
    assert first.url == "https://v.douyin.com/abc123/"
    assert first.title == "First & latest phone teardown clip."
    assert first.source_channel == "douyin:tech-reviewer"
    assert first.fetched_at.tzinfo is MODULE.UTC

    second = results[1]
    assert second.url == "https://v.douyin.com/def456/"
    assert second.title == "Second comparison video for a new gadget."
    assert second.source_channel == "douyin:device-lab"


@pytest.mark.asyncio
async def test_search_uses_aweme_id_fallback_when_share_url_missing() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": [
                    _video_entry(
                        aweme_id="7234567892",
                        desc="Fallback URL example.",
                        nickname="Fallback Creator",
                    )
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].url == "https://www.douyin.com/video/7234567892"


@pytest.mark.asyncio
async def test_search_skips_entry_without_aweme_info() -> None:
    client = _FakeTikhubClient({"data": {"data": [{"type": 4, "mix_info": {"id": "mix-1"}}]}})

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
    assert logger.events[0][0] == "douyin_tikhub_search_failed"
    assert SEARCH_PATH in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_handles_empty_desc_with_placeholder_title() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": [
                    _video_entry(
                        aweme_id="7234567893",
                        desc="",
                        nickname="Placeholder Creator",
                        share_url="https://v.douyin.com/ghi789/",
                    )
                ]
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].title == "Douyin video 7234567893"
    assert results[0].snippet is None
    assert results[0].content is None
