# Self-written, plan autosearch-0418-channels-and-skills.md § F003
import asyncio
from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="arxiv")

MAX_RESULTS = 10
HTTP_TIMEOUT = 30.0
BASE_URL = "https://export.arxiv.org/api/query"


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


async def search(query: SubQuery) -> list[Evidence]:
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(
                BASE_URL,
                params={
                    "search_query": f"all:{query.text}",
                    "start": 0,
                    "max_results": MAX_RESULTS,
                    "sortBy": "relevance",
                    "sortOrder": "descending",
                },
            )
            response.raise_for_status()

        feed = await asyncio.to_thread(feedparser.parse, response.text)
        if getattr(feed, "bozo", 0):
            bozo_exception = getattr(feed, "bozo_exception", None)
            raise ValueError(str(bozo_exception or "failed to parse Atom feed"))

        entries = list(getattr(feed, "entries", []))
        if not entries:
            raise ValueError("empty feed")
    except Exception as exc:
        LOGGER.warning("arxiv_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    return [_to_evidence(entry, fetched_at=fetched_at) for entry in entries]


def _to_evidence(entry: object, *, fetched_at: datetime) -> Evidence:
    title = _normalize_whitespace(str(getattr(entry, "title", "") or ""))
    summary = _normalize_whitespace(str(getattr(entry, "summary", "") or ""))
    url = str(getattr(entry, "link", "") or getattr(entry, "id", "") or "").strip()

    return Evidence(
        url=url,
        title=title,
        snippet=summary[:500] or None,
        source_channel="arxiv",
        fetched_at=fetched_at,
        score=0.0,
    )
