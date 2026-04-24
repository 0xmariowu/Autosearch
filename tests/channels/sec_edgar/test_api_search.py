from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import httpx
import pytest

from autosearch.core.models import SubQuery


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "sec_edgar"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_sec_edgar_api_search", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
search = MODULE.search


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _query() -> SubQuery:
    return SubQuery(text="research solutions 10-k", rationale="Need SEC filing coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_items_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/LATEST/search-index"
        assert request.url.params["q"] == "research solutions 10-k"
        return httpx.Response(
            200,
            json={
                "hits": {
                    "total": {"value": 2, "relation": "eq"},
                    "hits": [
                        {
                            "_id": "0001104659-25-091644:1",
                            "_source": {
                                "ciks": ["0001386301"],
                                "display_names": [
                                    "Research Solutions, Inc.  (RSSS)  (CIK 0001386301)"
                                ],
                                "adsh": "0001104659-25-091644",
                                "form": "10-K",
                                "file_date": "2025-09-19",
                                "period_ending": "2025-06-30",
                            },
                        },
                        {
                            "_id": "0000320193-25-000101:1",
                            "_source": {
                                "ciks": ["0000320193"],
                                "display_names": ["Apple Inc.  (AAPL)  (CIK 0000320193)"],
                                "adsh": "0000320193-25-000101",
                                "form": "8-K",
                                "file_date": "2025-10-31",
                            },
                        },
                    ],
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert (
        first.url
        == "https://www.sec.gov/Archives/edgar/data/1386301/000110465925091644/0001104659-25-091644-index.htm"
    )
    assert first.title == "Research Solutions, Inc.  (RSSS)  (CIK 0001386301) — 10-K"
    assert first.snippet == "10-K · filed 2025-09-19 · period ending 2025-06-30"
    assert first.content == first.snippet
    assert first.source_channel == "sec_edgar"

    second = results[1]
    assert (
        second.url
        == "https://www.sec.gov/Archives/edgar/data/320193/000032019325000101/0000320193-25-000101-index.htm"
    )
    assert second.title == "Apple Inc.  (AAPL)  (CIK 0000320193) — 8-K"
    assert second.snippet == "8-K · filed 2025-10-31"


@pytest.mark.asyncio
async def test_search_skips_items_without_source() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": {
                    "hits": [
                        {"_id": "missing-source"},
                        {
                            "_id": "valid",
                            "_source": {
                                "ciks": ["0001386301"],
                                "display_names": ["Research Solutions, Inc."],
                                "adsh": "0001104659-25-091644",
                                "form": "10-K",
                            },
                        },
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "Research Solutions, Inc. — 10-K"


@pytest.mark.asyncio
async def test_search_skips_items_without_ciks_or_adsh() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "display_names": ["Missing CIK"],
                                "adsh": "0001104659-25-091644",
                                "form": "10-K",
                            }
                        },
                        {
                            "_source": {
                                "ciks": ["0001386301"],
                                "display_names": ["Missing ADSH"],
                                "form": "10-Q",
                            }
                        },
                        {
                            "_source": {
                                "ciks": ["0001386301"],
                                "display_names": ["Valid Filing"],
                                "adsh": "0001104659-25-091644",
                                "form": "8-K",
                            }
                        },
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "Valid Filing — 8-K"


@pytest.mark.asyncio
async def test_search_falls_back_title_when_display_names_missing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "ciks": ["0001386301"],
                                "display_names": [],
                                "adsh": "0001104659-25-091644",
                                "form": "10-K",
                                "file_date": "2025-09-19",
                            }
                        }
                    ]
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "SEC filing · 10-K"
    assert results[0].snippet == "10-K · filed 2025-09-19"


@pytest.mark.asyncio
async def test_search_sends_required_user_agent_header() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json={"hits": {"hits": []}}, request=request)

    async with _client(handler) as http_client:
        await search(_query(), http_client=http_client)

    assert re.search(
        r"AutoSearch research-tool .*autosearch@0xmariowu\.github\.io",
        captured["user_agent"],
    )


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Bug 1 (fix-plan): typed exception now propagates instead of [].
    from autosearch.channels.base import (
        ChannelAuthError,
        PermanentError,
        RateLimited,
        TransientError,
    )

    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "boom"}, request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events
    assert logger.events[0][0] == "sec_edgar_search_failed"
    assert "500" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_handles_empty_hits() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}},
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
