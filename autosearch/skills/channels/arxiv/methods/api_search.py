# Self-written, plan autosearch-0418-channels-and-skills.md § F003
import asyncio
import time
from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="arxiv")

MAX_RESULTS = 10
HTTP_TIMEOUT = 30.0
BASE_URL = "https://export.arxiv.org/api/query"
RATE_LIMIT_RETRIES = 3
QUERY_CACHE_TTL_SECONDS = 300.0
QUERY_CACHE_MAX_ENTRIES = 200

_QUERY_CACHE: dict[str, tuple[list[Evidence], float]] = {}


class ArxivRateLimitError(Exception):
    """Raised when arXiv responds with a rate-limit body instead of Atom XML."""


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


async def search(query: SubQuery) -> list[Evidence]:
    cached_results = _get_cached_results(query.text)
    if cached_results is not None:
        return cached_results

    try:
        entries = await _search_entries_with_retry(query.text)
    except ArxivRateLimitError:
        LOGGER.warning("arxiv_search_failed", reason="rate_exceeded")
        return []
    except Exception as exc:
        LOGGER.warning("arxiv_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    results = [_to_evidence(entry, fetched_at=fetched_at) for entry in entries]
    _store_cached_results(query.text, results)
    return list(results)


async def _search_entries_with_retry(query_text: str) -> list[object]:
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            return await _fetch_entries(query_text)
        except ArxivRateLimitError:
            if attempt >= RATE_LIMIT_RETRIES:
                raise
            await asyncio.sleep(2**attempt)

    raise ArxivRateLimitError("rate_exceeded")


async def _fetch_entries(query_text: str) -> list[object]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(
            BASE_URL,
            params={
                "search_query": f"all:{query_text}",
                "start": 0,
                "max_results": MAX_RESULTS,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
        )
        response.raise_for_status()

    response_text = response.text
    if _is_rate_limited(response_text):
        raise ArxivRateLimitError("rate_exceeded")

    feed = await asyncio.to_thread(feedparser.parse, response_text)
    if getattr(feed, "bozo", 0):
        bozo_exception = getattr(feed, "bozo_exception", None)
        raise ValueError(str(bozo_exception or "failed to parse Atom feed"))

    entries = list(getattr(feed, "entries", []))
    if not entries:
        raise ValueError("empty feed")
    return entries


def _is_rate_limited(response_text: str) -> bool:
    return response_text.strip().startswith("Rate exceeded.")


def _get_cached_results(query_text: str) -> list[Evidence] | None:
    cached_entry = _QUERY_CACHE.get(query_text)
    if cached_entry is None:
        return None

    results, cached_at = cached_entry
    if (time.monotonic() - cached_at) > QUERY_CACHE_TTL_SECONDS:
        _QUERY_CACHE.pop(query_text, None)
        return None

    return list(results)


def _store_cached_results(query_text: str, results: list[Evidence]) -> None:
    _QUERY_CACHE.pop(query_text, None)
    _QUERY_CACHE[query_text] = (list(results), time.monotonic())

    while len(_QUERY_CACHE) > QUERY_CACHE_MAX_ENTRIES:
        oldest_query = next(iter(_QUERY_CACHE))
        _QUERY_CACHE.pop(oldest_query, None)


def _to_evidence(entry: object, *, fetched_at: datetime) -> Evidence:
    title = _normalize_whitespace(str(getattr(entry, "title", "") or ""))
    summary = _normalize_whitespace(str(getattr(entry, "summary", "") or ""))
    url = str(getattr(entry, "link", "") or getattr(entry, "id", "") or "").strip()

    # Bug 4: feedparser exposes the arxiv <published> tag — surface it so
    # recent_signal_fusion can rank papers by date.
    published_at: datetime | None = None
    published_raw = getattr(entry, "published", None)
    if published_raw:
        try:
            parsed = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
            published_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            published_at = None

    return Evidence(
        url=url,
        title=title,
        snippet=summary[:500] or None,
        source_channel="arxiv",
        fetched_at=fetched_at,
        published_at=published_at,
        score=0.0,
    )
