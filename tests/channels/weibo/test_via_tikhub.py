from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import cast

import httpx
import pytest

from autosearch.channels.base import PermanentError
from autosearch.core.models import SubQuery
from autosearch.lib.tikhub_client import TikhubClient


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "weibo"
        / "methods"
        / "via_tikhub.py"
    )
    spec = importlib.util.spec_from_file_location("test_weibo_via_tikhub", module_path)
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
    def __init__(self, token: str) -> None:
        self.token = token

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, object],
    ) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "detail": {
                    "message": f"upstream rejected Bearer {self.token}",
                    "token": self.token,
                    "headers": {"Authorization": f"Bearer {self.token}"},
                }
            },
            request=httpx.Request("GET", url, headers=headers, params=params),
        )


class _FailingTikhubClient:
    def __init__(self, token: str) -> None:
        self.client = TikhubClient(api_key="test-api-key", http_client=_FailingHTTPClient(token))

    async def get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        return await self.client.get(path, params)


def _query() -> SubQuery:
    return SubQuery(text="新能源车", rationale="Need Weibo reaction coverage")


@pytest.mark.asyncio
async def test_search_maps_card_type_9_mblogs_to_evidence() -> None:
    client = _FakeTikhubClient(
        {
            "code": 200,
            "data": {
                "ok": 1,
                "data": {
                    "cards": [
                        {
                            "card_type": 9,
                            "mblog": {
                                "id": 101,
                                "mid": 101,
                                "bid": "QBpBNjc3r",
                                "text": "首发体验 新能源车真不错",
                                "user": {"id": 123456, "screen_name": "AutoSearch"},
                            },
                        },
                        {
                            "card_type": 9,
                            "mblog": {
                                "id": 202,
                                "mid": 202,
                                "bid": "QBpCNjc3s",
                                "text": "补能效率比预期更稳。",
                                "user": {"id": 654321, "screen_name": "充电观察"},
                            },
                        },
                    ]
                },
            },
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert client.calls == [(SEARCH_PATH, {"keyword": "新能源车", "page": 1, "search_type": "1"})]
    assert len(results) == 2

    first = results[0]
    assert first.url == "https://weibo.com/123456/QBpBNjc3r"
    assert first.title == "@AutoSearch"
    assert first.snippet == "首发体验 新能源车真不错"
    assert first.content == "首发体验 新能源车真不错"
    assert first.source_channel == "weibo:tikhub"

    second = results[1]
    assert second.url == "https://weibo.com/654321/QBpCNjc3s"
    assert second.title == "@充电观察"
    assert second.snippet == "补能效率比预期更稳。"
    assert second.source_channel == "weibo:tikhub"


@pytest.mark.asyncio
async def test_search_extracts_nested_mblog_from_card_group() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": {
                    "cards": [
                        {
                            "card_type": 11,
                            "card_group": [
                                {"card_type": 42},
                                {
                                    "card_type": 9,
                                    "mblog": {
                                        "id": 303,
                                        "mid": 303,
                                        "mblogid": "QBpDNjc3t",
                                        "text": "车展现场人很多。",
                                        "user": {"id": 778899, "screen_name": "现场观察"},
                                    },
                                },
                            ],
                        }
                    ]
                }
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].url == "https://weibo.com/778899/QBpDNjc3t"
    assert results[0].title == "@现场观察"
    assert results[0].snippet == "车展现场人很多。"


@pytest.mark.asyncio
async def test_search_skips_cards_without_mblog() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": {
                    "cards": [
                        {"card_type": 11},
                        {"card_type": 9},
                        {"card_type": 17, "text": "ignored"},
                        {
                            "card_type": 9,
                            "mblog": {
                                "id": 404,
                                "mid": 404,
                                "bid": "QBpENjc3u",
                                "text": "真正的帖子。",
                                "user": {"id": 998877, "screen_name": "真实用户"},
                            },
                        },
                    ]
                }
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].url == "https://weibo.com/998877/QBpENjc3u"


@pytest.mark.asyncio
async def test_search_strips_html_tags_from_text() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": {
                    "cards": [
                        {
                            "card_type": 9,
                            "mblog": {
                                "id": 505,
                                "mid": 505,
                                "bid": "QBpFNjc3v",
                                "text": '<a href="/tag">#发布会#</a> <span>新品 &amp; 升级</span> <img alt="[笑]" src="x" />',
                                "user": {"id": 112233, "screen_name": "数码情报"},
                            },
                        }
                    ]
                }
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].snippet == "#发布会# 新品 & 升级"
    assert results[0].content == "#发布会# 新品 & 升级"


@pytest.mark.asyncio
async def test_search_falls_back_to_mid_url_when_bid_missing() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": {
                    "cards": [
                        {
                            "card_type": 9,
                            "mblog": {
                                "id": 606,
                                "mid": 4988776655443322,
                                "text": "只有 mid 的帖子。",
                                "user": {"screen_name": "移动端结果"},
                            },
                        }
                    ]
                }
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].url == "https://m.weibo.cn/detail/4988776655443322"


@pytest.mark.asyncio
async def test_search_raises_permanent_error_when_mblogs_present_but_none_parse() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": {
                    "cards": [
                        {
                            "card_type": 9,
                            "mblog": {
                                "id": 707,
                                "text": "没有 bid 也没有 mid。",
                                "user": {"screen_name": "无链接结果"},
                            },
                        }
                    ]
                }
            }
        }
    )

    with pytest.raises(PermanentError, match="items present but none parsed"):
        await search(_query(), client=cast(TikhubClient, client))


@pytest.mark.asyncio
async def test_search_raises_permanent_error_when_cards_present_but_no_mblogs_parse() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": {
                    "cards": [
                        {
                            "card_type": 9,
                            "blog": {
                                "id": 909,
                                "mid": 909,
                                "bid": "QBpHNjc3x",
                                "text": "mblog field was renamed.",
                                "user": {"id": 112244, "screen_name": "SchemaDrift"},
                            },
                        }
                    ]
                }
            }
        }
    )

    with pytest.raises(PermanentError, match="items present but none parsed"):
        await search(_query(), client=cast(TikhubClient, client))


@pytest.mark.asyncio
async def test_search_raises_on_invalid_payload_shape() -> None:
    client = _FakeTikhubClient({"data": {"data": {"unexpected": []}}})

    with pytest.raises(PermanentError, match="invalid payload shape"):
        await search(_query(), client=cast(TikhubClient, client))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload"),
    [
        {},
        {"data": []},
        {"data": {"data": []}},
    ],
)
async def test_search_raises_on_missing_or_invalid_nested_data_shape(
    payload: dict[str, object],
) -> None:
    client = _FakeTikhubClient(payload)

    with pytest.raises(PermanentError, match="invalid payload shape"):
        await search(_query(), client=cast(TikhubClient, client))


@pytest.mark.asyncio
async def test_search_allows_legitimate_empty_cards_list() -> None:
    client = _FakeTikhubClient({"data": {"data": {"cards": []}}})

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
        await search(
            _query(),
            client=cast(TikhubClient, _FailingTikhubClient("secret-token-xyz")),
        )

    assert logger.events
    assert logger.events[0][0] == "weibo_tikhub_search_failed"
    reason = str(logger.events[0][1]["reason"])
    assert SEARCH_PATH in reason
    assert "Bearer" not in reason
    assert "secret-token-xyz" not in reason


@pytest.mark.asyncio
async def test_search_truncates_long_text_to_snippet() -> None:
    long_text = ("word " * 59) + "splitpoint continues after the limit"
    client = _FakeTikhubClient(
        {
            "data": {
                "data": {
                    "cards": [
                        {
                            "card_type": 9,
                            "mblog": {
                                "id": 808,
                                "mid": 808,
                                "bid": "QBpGNjc3w",
                                "text": long_text,
                                "user": {"id": 445566, "screen_name": "LongPost"},
                            },
                        }
                    ]
                }
            }
        }
    )

    results = await search(_query(), client=cast(TikhubClient, client))

    assert len(results) == 1
    assert results[0].snippet == f"{('word ' * 59).strip()}…"
    assert results[0].content == long_text
