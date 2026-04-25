from __future__ import annotations

import importlib.util
from datetime import UTC
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
        / "zhihu"
        / "methods"
        / "via_tikhub.py"
    )
    spec = importlib.util.spec_from_file_location("test_zhihu_via_tikhub", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
SEARCH_PATH = MODULE.SEARCH_PATH
search = MODULE.search


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


@pytest.mark.asyncio
async def test_search_maps_tikhub_articles_to_evidence() -> None:
    client = _FakeTikhubClient(
        {
            "data": {
                "data": [
                    {
                        "object": {
                            "id": "123456",
                            "title": "<em>LLM</em> Agent 实战",
                            "excerpt": "最好的 <b>Agent</b> 文章",
                            "content": "<p>完整 <strong>内容</strong></p>",
                        }
                    },
                    {
                        "object": {
                            "url": "https://zhuanlan.zhihu.com/p/654321",
                            "title": "第二篇",
                            "excerpt": "<p>摘要</p>",
                        }
                    },
                ]
            }
        }
    )

    results = await search(
        SubQuery(text="LLM agent", rationale="Need Zhihu article coverage"),
        client=cast(TikhubClient, client),
    )

    assert client.calls == [(SEARCH_PATH, {"keyword": "LLM agent"})]
    assert len(results) == 2

    first = results[0]
    assert first.title == "LLM Agent 实战"
    assert first.url == "https://zhuanlan.zhihu.com/p/123456"
    assert first.snippet == "最好的 Agent 文章"
    assert first.content == "完整 内容"
    assert first.source_channel == "zhihu:tikhub"
    assert first.fetched_at.tzinfo is UTC

    second = results[1]
    assert second.title == "第二篇"
    assert second.url == "https://zhuanlan.zhihu.com/p/654321"
    assert second.snippet == "摘要"
    assert second.content == "摘要"


@pytest.mark.asyncio
async def test_search_raises_typed_error_on_tikhub_error() -> None:
    # Bug 1 (fix-plan): typed exception now propagates instead of [].
    from autosearch.channels.base import TransientError

    with pytest.raises(TransientError):
        await search(
            SubQuery(text="LLM agent", rationale="Need Zhihu article coverage"),
            client=cast(TikhubClient, _FailingTikhubClient()),
        )


@pytest.mark.asyncio
async def test_search_raises_permanent_error_on_malformed_payload() -> None:
    client = _FakeTikhubClient({"data": {"data": {"unexpected": []}}})

    with pytest.raises(PermanentError, match="invalid payload shape"):
        await search(
            SubQuery(text="LLM agent", rationale="Need Zhihu article coverage"),
            client=cast(TikhubClient, client),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload"),
    [
        {},
        {"data": []},
    ],
)
async def test_search_raises_permanent_error_when_data_container_is_missing_or_invalid(
    payload: dict[str, object],
) -> None:
    client = _FakeTikhubClient(payload)

    with pytest.raises(PermanentError, match="invalid payload shape"):
        await search(
            SubQuery(text="LLM agent", rationale="Need Zhihu article coverage"),
            client=cast(TikhubClient, client),
        )


@pytest.mark.asyncio
async def test_search_allows_legitimate_empty_article_list() -> None:
    client = _FakeTikhubClient({"data": {"data": []}})

    results = await search(
        SubQuery(text="LLM agent", rationale="Need Zhihu article coverage"),
        client=cast(TikhubClient, client),
    )

    assert results == []
