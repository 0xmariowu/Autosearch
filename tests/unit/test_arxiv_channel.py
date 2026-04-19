import re
from pathlib import Path

import httpx
import pytest

from autosearch.channels.base import ChannelRegistry, Environment
from autosearch.core.models import Evidence, SubQuery

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _fixture_text(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _channels_root() -> Path:
    return Path(__file__).resolve().parents[2] / "autosearch" / "skills" / "channels"


def _compiled_arxiv():
    registry = ChannelRegistry.compile_from_skills(_channels_root(), Environment())
    return registry, registry.metadata("arxiv").methods[0].callable


def _response(
    text: str,
    *,
    status_code: int = 200,
    url: str = "https://export.arxiv.org/api/query",
    params: dict[str, object] | None = None,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        text=text,
        request=httpx.Request("GET", url, params=params),
    )


@pytest.mark.asyncio
async def test_search_returns_evidence_from_atom_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    registry, search_callable = _compiled_arxiv()

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        captured["url"] = url
        captured["params"] = dict(params)
        return _response(_fixture_text("arxiv_response.atom"), url=url, params=params)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)

    results = await registry.get("arxiv").search(
        SubQuery(text="retrieval augmented generation", rationale="Need paper coverage")
    )

    assert len(results) == 3
    assert all(isinstance(item, Evidence) for item in results)
    assert re.compile(r"^https?://arxiv\.org/abs/").search(results[0].url)
    assert all(re.compile(r"^https?://arxiv\.org/abs/").search(item.url) for item in results)
    assert captured["url"] == "https://export.arxiv.org/api/query"
    assert captured["params"] == {
        "search_query": "all:retrieval augmented generation",
        "start": 0,
        "max_results": 10,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    assert all(item.source_channel == "arxiv" for item in results)
    assert all(item.score == 0.0 for item in results)


@pytest.mark.asyncio
async def test_search_empty_feed_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    registry, search_callable = _compiled_arxiv()

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        return _response(
            """<?xml version="1.0" encoding="UTF-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
              <id>http://arxiv.org/api/query</id>
              <title>Empty</title>
              <updated>2026-04-18T00:00:00Z</updated>
            </feed>
            """,
            url=url,
            params=params,
        )

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)
    monkeypatch.setitem(search_callable.__globals__, "LOGGER", logger)

    results = await registry.get("arxiv").search(
        SubQuery(text="retrieval augmented generation", rationale="Need paper coverage")
    )

    assert results == []
    assert logger.events == [
        (
            "arxiv_search_failed",
            {"reason": "empty feed"},
        )
    ]


@pytest.mark.asyncio
async def test_search_handles_network_error_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    registry, search_callable = _compiled_arxiv()

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        _ = params
        raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)
    monkeypatch.setitem(search_callable.__globals__, "LOGGER", logger)

    results = await registry.get("arxiv").search(
        SubQuery(text="rag", rationale="Need paper coverage")
    )

    assert results == []
    assert logger.events == [
        (
            "arxiv_search_failed",
            {"reason": "boom"},
        )
    ]


@pytest.mark.asyncio
async def test_search_handles_parse_error_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    registry, search_callable = _compiled_arxiv()

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        return _response("<feed><entry>", url=url, params=params)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)
    monkeypatch.setitem(search_callable.__globals__, "LOGGER", logger)

    results = await registry.get("arxiv").search(
        SubQuery(text="rag", rationale="Need paper coverage")
    )

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "arxiv_search_failed"
    assert "reason" in logger.events[0][1]


@pytest.mark.asyncio
async def test_snippet_truncated_to_500_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    registry, search_callable = _compiled_arxiv()

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        return _response(_fixture_text("arxiv_response.atom"), url=url, params=params)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)

    results = await registry.get("arxiv").search(
        SubQuery(text="retrieval augmented generation", rationale="Need paper coverage")
    )

    assert len(results) == 3
    assert results[1].snippet is not None
    assert len(results[1].snippet) == 500


@pytest.mark.asyncio
async def test_title_whitespace_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    registry, search_callable = _compiled_arxiv()

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        return _response(_fixture_text("arxiv_response.atom"), url=url, params=params)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)

    results = await registry.get("arxiv").search(
        SubQuery(text="retrieval augmented generation", rationale="Need paper coverage")
    )

    assert len(results) == 3
    assert results[2].title == "Chain-of-Thought Prompting for Retrieval Systems"
    assert "\n" not in results[2].title
    assert "  " not in results[2].title
