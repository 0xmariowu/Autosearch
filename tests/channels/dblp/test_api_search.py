# Self-written for task Plan-0420 W7 F701 + F702
from __future__ import annotations

import importlib.util
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
        / "dblp"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_dblp_api_search", module_path)
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
    return SubQuery(text="transformer attention", rationale="Need CS bibliography coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _truncate_expected(text: str, *, max_length: int = 300) -> str:
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    if candidate and not candidate[-1].isspace():
        shortened = candidate.rsplit(None, 1)[0]
        if shortened:
            candidate = shortened

    return f"{candidate.rstrip()}…"


@pytest.mark.asyncio
async def test_search_maps_dblp_hits_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "transformer attention"
        assert request.url.params["h"] == "10"
        assert request.url.params["format"] == "json"
        assert request.headers["accept"] == "application/json"
        return httpx.Response(
            200,
            json={
                "result": {
                    "hits": {
                        "hit": [
                            {
                                "@score": "1.0",
                                "@id": "1",
                                "url": "https://dblp.org/rec/conf/nips/VaswaniSPUJGKP17",
                                "info": {
                                    "title": "Attention Is All You Need.",
                                    "authors": {
                                        "author": [
                                            {"text": "Ashish Vaswani"},
                                            {"text": "Noam Shazeer"},
                                            {"text": "Niki Parmar"},
                                            {"text": "Jakob Uszkoreit"},
                                        ]
                                    },
                                    "venue": "NeurIPS",
                                    "year": "2017",
                                    "type": "Conference and Workshop Papers",
                                    "ee": "https://doi.org/10.5555/3295222.3295349",
                                    "url": "https://dblp.org/rec/conf/nips/VaswaniSPUJGKP17",
                                },
                            },
                            {
                                "@score": "0.9",
                                "@id": "2",
                                "url": "https://dblp.org/rec/journals/corr/abs-2401-12345",
                                "info": {
                                    "title": "Transformers in Practice.",
                                    "authors": {"author": {"text": "Alice Researcher"}},
                                    "venue": "CoRR",
                                    "year": "2024",
                                    "type": "Journal Articles",
                                    "url": "https://dblp.org/rec/journals/corr/abs-2401-12345",
                                },
                            },
                        ]
                    }
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://doi.org/10.5555/3295222.3295349"
    assert first.title == "Attention Is All You Need"
    assert (
        first.snippet
        == "Ashish Vaswani, Noam Shazeer, Niki Parmar · NeurIPS · 2017 · Conference and Workshop Papers"
    )
    assert first.content == first.snippet
    assert first.source_channel == "dblp"

    second = results[1]
    assert second.url == "https://dblp.org/rec/journals/corr/abs-2401-12345"
    assert second.title == "Transformers in Practice"
    assert second.snippet == "Alice Researcher · CoRR · 2024 · Journal Articles"


@pytest.mark.asyncio
async def test_search_skips_hits_without_title_or_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "hits": {
                        "hit": [
                            {
                                "info": {
                                    "title": "",
                                    "authors": {"author": [{"text": "Missing Title"}]},
                                    "url": "https://dblp.org/rec/skip-title",
                                }
                            },
                            {
                                "info": {
                                    "title": "Missing URL.",
                                    "authors": {"author": [{"text": "Missing Url"}]},
                                }
                            },
                            {
                                "info": {
                                    "title": "Valid Entry.",
                                    "authors": {"author": [{"text": "Valid Author"}]},
                                    "venue": "ICML",
                                    "year": "2024",
                                    "type": "Conference and Workshop Papers",
                                    "url": "https://dblp.org/rec/conf/icml/valid24",
                                }
                            },
                        ]
                    }
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "Valid Entry"
    assert results[0].url == "https://dblp.org/rec/conf/icml/valid24"


@pytest.mark.asyncio
async def test_search_falls_back_to_info_url_when_ee_missing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "hits": {
                        "hit": {
                            "info": {
                                "title": "Fallback URL.",
                                "authors": {"author": [{"text": "Fallback Author"}]},
                                "venue": "ACL",
                                "year": "2024",
                                "type": "Conference and Workshop Papers",
                                "url": "https://dblp.org/rec/conf/acl/fallback24",
                            }
                        }
                    }
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://dblp.org/rec/conf/acl/fallback24"


@pytest.mark.asyncio
async def test_search_handles_empty_hits() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": {"hits": {"hit": []}}}, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []


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
        return httpx.Response(503, json={"error": "unavailable"}, request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events
    assert logger.events[0][0] == "dblp_search_failed"
    assert "503" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_truncates_long_synthesized_snippet() -> None:
    long_venue = ("VeryLongVenueName " * 20).strip()
    long_type = ("LongTypeLabel " * 15).strip()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "hits": {
                        "hit": [
                            {
                                "info": {
                                    "title": "Long Metadata.",
                                    "authors": {"author": [{"text": "word"} for _ in range(120)]},
                                    "venue": long_venue,
                                    "year": "2025",
                                    "type": long_type,
                                    "url": "https://dblp.org/rec/conf/test/long25",
                                }
                            }
                        ]
                    }
                }
            },
            request=request,
        )

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    expected = _truncate_expected(f"word, word, word · {long_venue} · 2025 · {long_type}")
    assert len(results) == 1
    assert results[0].snippet == expected
    assert results[0].content == expected
    assert results[0].snippet is not None
    assert results[0].snippet.endswith("…")
