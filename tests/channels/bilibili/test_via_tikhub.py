# Self-written for task F205
from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from autosearch.channels.base import PermanentError
from autosearch.core.models import SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "bilibili"
        / "methods"
        / "via_tikhub.py"
    )
    spec = importlib.util.spec_from_file_location("test_bilibili_via_tikhub", module_path)
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
    return SubQuery(text="AI教程", rationale="Need Bilibili video and article coverage")


def _payload(result_groups: list[dict[str, object]]) -> dict[str, object]:
    return {"data": {"data": {"result": result_groups}}}


def _group(result_type: str, items: list[dict[str, object]]) -> dict[str, object]:
    return {"result_type": result_type, "data": items}


def _video_item(
    *,
    bvid: str,
    title: str,
    description: str,
    author: str,
    arcurl: str | None = None,
) -> dict[str, object]:
    item = {
        "bvid": bvid,
        "aid": 1234567890,
        "title": title,
        "description": description,
        "author": author,
        "mid": 12345,
        "play": 123456,
        "video_review": 89,
        "pubdate": 1713546000,
        "duration": "5:32",
    }
    if arcurl is not None:
        item["arcurl"] = arcurl
    return item


def _article_item(
    *,
    article_id: int | str,
    title: str,
    summary: str,
    author_name: str,
    url: str | None = None,
) -> dict[str, object]:
    item = {
        "id": article_id,
        "title": title,
        "summary": summary,
        "author_name": author_name,
    }
    if url is not None:
        item["url"] = url
    return item


@pytest.mark.asyncio
async def test_search_extracts_videos_from_result_groups() -> None:
    client = _FakeTikhubClient(
        _payload(
            [
                _group(
                    "video",
                    [
                        _video_item(
                            bvid="BV1abc123",
                            title="Video title one",
                            description="First description.",
                            author="UP One",
                            arcurl="https://www.bilibili.com/video/BV1abc123",
                        ),
                        _video_item(
                            bvid="BV2xyz456",
                            title="Video title two",
                            description="Second description.",
                            author="UP Two",
                        ),
                    ],
                )
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert client.calls == [
        (
            SEARCH_PATH,
            {
                "keyword": "AI教程",
                "search_type": "video",
                "order": "totalrank",
                "page": 1,
                "page_size": 10,
            },
        )
    ]
    assert len(results) == 2
    assert results[0].url == "https://www.bilibili.com/video/BV1abc123"
    assert results[1].url == "https://www.bilibili.com/video/BV2xyz456"
    assert results[0].source_channel == "bilibili:video:up-one"
    assert results[1].source_channel == "bilibili:video:up-two"
    assert results[0].published_at == datetime(2024, 4, 19, 17, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_search_extracts_articles_from_result_groups() -> None:
    client = _FakeTikhubClient(
        _payload(
            [
                _group(
                    "article",
                    [
                        _article_item(
                            article_id=445566,
                            title="Article title",
                            summary="Article summary text.",
                            author_name="Tech Writer",
                        )
                    ],
                )
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].url == "https://www.bilibili.com/read/cv445566/"
    assert results[0].source_channel == "bilibili:article:tech-writer"


@pytest.mark.asyncio
async def test_search_missing_pubdate_sets_published_at_none() -> None:
    item = _video_item(
        bvid="BV5missing222",
        title="Missing pubdate",
        description="No publish timestamp.",
        author="No Date",
    )
    item.pop("pubdate")
    client = _FakeTikhubClient(_payload([_group("video", [item])]))

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].published_at is None


@pytest.mark.asyncio
async def test_search_strips_em_markers_from_title_and_description() -> None:
    client = _FakeTikhubClient(
        _payload(
            [
                _group(
                    "video",
                    [
                        _video_item(
                            bvid="BV3strip789",
                            title="<em class='keyword'>foo</em> bar",
                            description="desc <em class='keyword'>foo</em> bar",
                            author="Markup Cleaner",
                        )
                    ],
                )
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].title == "foo bar"
    assert results[0].snippet == "desc foo bar"
    assert results[0].content == "desc foo bar"


@pytest.mark.asyncio
async def test_search_ignores_user_and_live_result_types() -> None:
    client = _FakeTikhubClient(
        _payload(
            [
                _group("bili_user", [{"uname": "Not evidence"}]),
                _group("live", [{"title": "Live stream"}]),
                _group(
                    "video",
                    [
                        _video_item(
                            bvid="BV4keep111",
                            title="Kept result",
                            description="Only this one should survive.",
                            author="Signal Only",
                        )
                    ],
                ),
            ]
        )
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].title == "Kept result"
    assert results[0].source_channel == "bilibili:video:signal-only"


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
    assert logger.events[0][0] == "bilibili_tikhub_search_failed"
    assert SEARCH_PATH in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_raises_permanent_error_on_malformed_payload() -> None:
    client = _FakeTikhubClient({"data": {"data": {"unexpected": []}}})

    with pytest.raises(PermanentError, match="invalid payload shape"):
        await search(_query(), client=cast(TikhubClient, client))
