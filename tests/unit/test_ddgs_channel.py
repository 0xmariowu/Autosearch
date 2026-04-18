# Self-written, plan autosearch-0418-channels-and-skills.md § F003
from datetime import datetime
from pathlib import Path

import pytest

from autosearch.channels.base import ChannelRegistry, Environment
from autosearch.core.models import Evidence, SubQuery


class _FakeDDGS:
    def __init__(
        self,
        results: list[dict[str, str]] | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._results = results or []
        self._exc = exc

    def text(
        self,
        query: str,
        *,
        max_results: int,
        region: str,
        safesearch: str,
    ) -> list[dict[str, str]]:
        _ = query
        _ = max_results
        _ = region
        _ = safesearch
        if self._exc is not None:
            raise self._exc
        return list(self._results)


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _channels_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "channels"


def _compiled_ddgs():
    registry = ChannelRegistry.compile_from_skills(_channels_root(), Environment())
    return registry, registry.metadata("ddgs").methods[0].callable


@pytest.mark.asyncio
async def test_search_returns_evidence_list(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_hits = [
        {"title": "Title 1", "href": "https://example.com/1", "body": "Snippet 1"},
        {"title": "Title 2", "href": "https://example.com/2", "body": "Snippet 2"},
        {"title": "Title 3", "href": "https://example.com/3", "body": "Snippet 3"},
    ]
    registry, search_callable = _compiled_ddgs()
    monkeypatch.setitem(search_callable.__globals__, "DDGS", lambda: _FakeDDGS(results=fake_hits))

    results = await registry.get("ddgs").search(SubQuery(text="bm25", rationale="Need web results"))

    assert len(results) == 3
    assert all(isinstance(item, Evidence) for item in results)
    assert [item.url for item in results] == [hit["href"] for hit in fake_hits]
    assert [item.title for item in results] == [hit["title"] for hit in fake_hits]
    assert [item.snippet for item in results] == [hit["body"] for hit in fake_hits]
    assert all(item.source_channel == "ddgs" for item in results)
    assert all(item.score == 0.0 for item in results)
    assert all(isinstance(item.fetched_at, datetime) for item in results)


@pytest.mark.asyncio
async def test_search_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    registry, search_callable = _compiled_ddgs()
    monkeypatch.setitem(search_callable.__globals__, "DDGS", lambda: _FakeDDGS(results=[]))

    results = await registry.get("ddgs").search(SubQuery(text="bm25", rationale="Need web results"))

    assert results == []


@pytest.mark.asyncio
async def test_search_handles_exception_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    registry, search_callable = _compiled_ddgs()
    monkeypatch.setitem(
        search_callable.__globals__, "DDGS", lambda: _FakeDDGS(exc=RuntimeError("boom"))
    )
    monkeypatch.setitem(search_callable.__globals__, "LOGGER", logger)

    results = await registry.get("ddgs").search(SubQuery(text="bm25", rationale="Need web results"))

    assert results == []
    assert logger.events == [
        (
            "ddgs_search_failed",
            {"reason": "boom"},
        )
    ]


@pytest.mark.asyncio
async def test_snippet_truncated_to_500_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    long_body = "x" * 750
    registry, search_callable = _compiled_ddgs()
    monkeypatch.setitem(
        search_callable.__globals__,
        "DDGS",
        lambda: _FakeDDGS(
            results=[
                {
                    "title": "Long body",
                    "href": "https://example.com/long",
                    "body": long_body,
                }
            ]
        ),
    )

    results = await registry.get("ddgs").search(SubQuery(text="bm25", rationale="Need web results"))

    assert len(results) == 1
    assert results[0].snippet is not None
    assert len(results[0].snippet) == 500
