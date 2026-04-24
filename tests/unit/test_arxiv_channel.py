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


def _subquery(text: str) -> SubQuery:
    return SubQuery(text=text, rationale="Need paper coverage")


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

    results = await registry.get("arxiv").search(_subquery("retrieval augmented generation"))

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

    results = await registry.get("arxiv").search(_subquery("retrieval augmented generation"))

    # Bug 1 (fix-plan): an empty feed is a legitimate "no results" — channel
    # returns [] without raising, MCP boundary surfaces status="no_results".
    assert results == []
    assert logger.events == []


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

    # Bug 1 (fix-plan): network failure now raises TransientError so the host
    # agent can distinguish a transient blip from "actually no results".
    from autosearch.channels.base import TransientError

    with pytest.raises(TransientError):
        await registry.get("arxiv").search(_subquery("rag"))
    assert logger.events
    assert logger.events[0][0] == "arxiv_search_failed"


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

    # Bug 1 (fix-plan): malformed feed → typed PermanentError, not silent [].
    from autosearch.channels.base import PermanentError

    with pytest.raises(PermanentError):
        await registry.get("arxiv").search(_subquery("rag"))
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

    results = await registry.get("arxiv").search(_subquery("retrieval augmented generation"))

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

    results = await registry.get("arxiv").search(_subquery("retrieval augmented generation"))

    assert len(results) == 3
    assert results[2].title == "Chain-of-Thought Prompting for Retrieval Systems"
    assert "\n" not in results[2].title
    assert "  " not in results[2].title


@pytest.mark.asyncio
async def test_arxiv_rate_exceeded_body_triggers_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, search_callable = _compiled_arxiv()
    sleep_calls: list[int] = []
    call_count = 0
    responses = [
        "Rate exceeded.",
        _fixture_text("arxiv_response.atom"),
    ]

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        nonlocal call_count
        call_count += 1
        return _response(responses.pop(0), url=url, params=params)

    async def fake_sleep(delay: int) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)
    monkeypatch.setattr(search_callable.__globals__["asyncio"], "sleep", fake_sleep)

    results = await registry.get("arxiv").search(_subquery("retry query"))

    assert len(results) == 3
    assert call_count == 2
    assert sleep_calls == [1]


@pytest.mark.asyncio
async def test_arxiv_rate_exceeded_exhausts_retries_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    registry, search_callable = _compiled_arxiv()
    call_count = 0

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        nonlocal call_count
        call_count += 1
        return _response("Rate exceeded.", url=url, params=params)

    async def fake_sleep(delay: int) -> None:
        _ = delay

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)
    monkeypatch.setattr(search_callable.__globals__["asyncio"], "sleep", fake_sleep)
    monkeypatch.setitem(search_callable.__globals__, "LOGGER", logger)

    # Bug 1 (fix-plan): rate limit exhaustion now raises RateLimited so the
    # host agent can backoff intentionally rather than treating it as empty.
    from autosearch.channels.base import RateLimited

    with pytest.raises(RateLimited):
        await registry.get("arxiv").search(_subquery("retry query"))
    assert call_count == 4
    assert logger.events == [
        (
            "arxiv_search_failed",
            {"reason": "rate_exceeded"},
        )
    ]


@pytest.mark.asyncio
async def test_arxiv_rate_exceeded_backoff_doubles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, search_callable = _compiled_arxiv()
    sleep_calls: list[int] = []

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        return _response("Rate exceeded.", url=url, params=params)

    async def fake_sleep(delay: int) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)
    monkeypatch.setattr(search_callable.__globals__["asyncio"], "sleep", fake_sleep)

    # Bug 1 (fix-plan): rate-limit exhaustion raises RateLimited.
    from autosearch.channels.base import RateLimited

    with pytest.raises(RateLimited):
        await registry.get("arxiv").search(_subquery("retry query"))
    assert sleep_calls == [1, 2, 4]


@pytest.mark.asyncio
async def test_arxiv_cache_hit_skips_http(monkeypatch: pytest.MonkeyPatch) -> None:
    registry, search_callable = _compiled_arxiv()
    call_count = 0

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        nonlocal call_count
        call_count += 1
        return _response(_fixture_text("arxiv_response.atom"), url=url, params=params)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)

    first_results = await registry.get("arxiv").search(_subquery("cached query"))
    second_results = await registry.get("arxiv").search(_subquery("cached query"))

    assert len(first_results) == 3
    assert second_results == first_results
    assert call_count == 1


@pytest.mark.asyncio
async def test_arxiv_cache_respects_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    registry, search_callable = _compiled_arxiv()
    call_count = 0
    now = {"value": 100.0}

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        nonlocal call_count
        call_count += 1
        return _response(_fixture_text("arxiv_response.atom"), url=url, params=params)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)
    monkeypatch.setattr(search_callable.__globals__["time"], "monotonic", lambda: now["value"])

    first_results = await registry.get("arxiv").search(_subquery("ttl query"))
    now["value"] = 401.0
    second_results = await registry.get("arxiv").search(_subquery("ttl query"))

    assert len(first_results) == 3
    assert len(second_results) == 3
    assert call_count == 2


@pytest.mark.asyncio
async def test_arxiv_cache_different_query_not_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, search_callable = _compiled_arxiv()
    call_count = 0

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        nonlocal call_count
        call_count += 1
        return _response(_fixture_text("arxiv_response.atom"), url=url, params=params)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)

    first_results = await registry.get("arxiv").search(_subquery("query A"))
    second_results = await registry.get("arxiv").search(_subquery("query B"))

    assert len(first_results) == 3
    assert len(second_results) == 3
    assert call_count == 2


@pytest.mark.asyncio
async def test_arxiv_cache_does_not_store_rate_limit_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    registry, search_callable = _compiled_arxiv()
    call_count = 0
    responses = [
        "Rate exceeded.",
        "Rate exceeded.",
        "Rate exceeded.",
        "Rate exceeded.",
        _fixture_text("arxiv_response.atom"),
    ]

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        nonlocal call_count
        call_count += 1
        return _response(responses.pop(0), url=url, params=params)

    async def fake_sleep(delay: int) -> None:
        _ = delay

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)
    monkeypatch.setattr(search_callable.__globals__["asyncio"], "sleep", fake_sleep)
    monkeypatch.setitem(search_callable.__globals__, "LOGGER", logger)

    # Bug 1 (fix-plan): rate-limit failures raise RateLimited; verify they
    # ALSO don't poison the cache so a follow-up succeeds.
    from autosearch.channels.base import RateLimited

    with pytest.raises(RateLimited):
        await registry.get("arxiv").search(_subquery("retry query"))
    assert search_callable.__globals__["_QUERY_CACHE"] == {}

    second_results = await registry.get("arxiv").search(_subquery("retry query"))

    assert len(second_results) == 3
    assert call_count == 5


@pytest.mark.asyncio
async def test_arxiv_cache_size_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    registry, search_callable = _compiled_arxiv()
    call_count = 0

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        nonlocal call_count
        call_count += 1
        return _response(_fixture_text("arxiv_response.atom"), url=url, params=params)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)

    for index in range(201):
        await registry.get("arxiv").search(_subquery(f"query-{index}"))

    cache = search_callable.__globals__["_QUERY_CACHE"]

    assert len(cache) == 200
    assert "query-0" not in cache
    assert "query-1" in cache
    assert "query-200" in cache
    assert call_count == 201


@pytest.mark.asyncio
async def test_arxiv_valid_xml_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    registry, search_callable = _compiled_arxiv()

    async def fake_get(self, url: str, *, params: dict[str, object]) -> httpx.Response:
        _ = self
        return _response(_fixture_text("arxiv_response.atom"), url=url, params=params)

    monkeypatch.setattr(search_callable.__globals__["httpx"].AsyncClient, "get", fake_get)

    results = await registry.get("arxiv").search(_subquery("xml query"))

    assert len(results) == 3
    assert all(item.source_channel == "arxiv" for item in results)
