# Self-written for task F202
from __future__ import annotations

import asyncio
import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from autosearch.channels.base import raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="google_news")

BASE_URL = "https://news.google.com/rss/search"
HTTP_TIMEOUT = 15.0
MAX_RESULTS = 10
MAX_SNIPPET_LENGTH = 300
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch)"
REQUEST_HEADERS = {
    "Accept": "application/rss+xml, application/xml, text/xml",
    "User-Agent": USER_AGENT,
}
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
NON_SLUG_CHAR_RE = re.compile(r"[^a-z0-9-]+")
MULTI_HYPHEN_RE = re.compile(r"-+")


def _truncate_on_word_boundary(text: str, *, max_length: int) -> str:
    text = text.strip()
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    if candidate and not candidate[-1].isspace():
        shortened = candidate.rsplit(None, 1)[0]
        if shortened:
            candidate = shortened

    return f"{candidate.rstrip()}…"


def _normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def _clean_summary(summary: object) -> str | None:
    cleaned = html.unescape(str(summary or ""))
    cleaned = TAG_RE.sub(" ", cleaned)
    cleaned = _normalize_whitespace(cleaned)
    if not cleaned:
        return None
    return _truncate_on_word_boundary(cleaned, max_length=MAX_SNIPPET_LENGTH) or None


def _sanitize_publisher(publisher: str) -> str:
    slug = html.unescape(publisher).lower().strip()
    if not slug:
        return ""

    slug = re.sub(r"\s+", "-", slug)
    slug = NON_SLUG_CHAR_RE.sub("", slug)
    slug = MULTI_HYPHEN_RE.sub("-", slug).strip("-")
    return slug


def _publisher_title(entry: object) -> str:
    source = getattr(entry, "source", None)
    if isinstance(source, Mapping):
        return str(source.get("title") or "").strip()

    if source is not None:
        return str(getattr(source, "title", "") or "").strip()

    getter = getattr(entry, "get", None)
    if callable(getter):
        source = getter("source", {})
        if isinstance(source, Mapping):
            return str(source.get("title") or "").strip()

    return ""


def _to_evidence(entry: object, *, fetched_at: datetime) -> Evidence | None:
    url = str(getattr(entry, "link", "") or "").strip()
    if not url:
        return None

    title = _normalize_whitespace(html.unescape(str(getattr(entry, "title", "") or "").strip()))
    snippet = _clean_summary(getattr(entry, "summary", ""))
    publisher = _publisher_title(entry)
    publisher_slug = _sanitize_publisher(publisher)
    source_channel = f"google_news:{publisher_slug}" if publisher_slug else "google_news"

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=snippet,
        source_channel=source_channel,
        fetched_at=fetched_at,
        score=0.0,
    )


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    params = {
        "q": query.text,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    try:
        if http_client is not None:
            response = await http_client.get(BASE_URL, params=params, headers=REQUEST_HEADERS)
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(BASE_URL, params=params, headers=REQUEST_HEADERS)

        response.raise_for_status()
        feed = await asyncio.to_thread(feedparser.parse, response.text)
    except Exception as exc:
        LOGGER.warning("google_news_search_failed", reason=str(exc))
        raise_as_channel_error(exc)

    if getattr(feed, "bozo", 0) == 1:
        reason = str(getattr(feed, "bozo_exception", None) or "failed to parse RSS feed")
        LOGGER.warning("google_news_search_failed", reason=reason)
        return []

    entries = list(getattr(feed, "entries", []))[:MAX_RESULTS]
    if not entries:
        return []

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for entry in entries:
        evidence = _to_evidence(entry, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
