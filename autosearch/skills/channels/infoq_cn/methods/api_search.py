# Self-written for task F204
from __future__ import annotations

import asyncio
import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="infoq_cn")

BASE_URL = "https://www.infoq.cn/feed"
HTTP_TIMEOUT = 15.0
MAX_RESULTS = 10
MAX_SNIPPET_LENGTH = 300
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch)"
REQUEST_HEADERS = {
    "Accept": "application/rss+xml, application/xml",
    "User-Agent": USER_AGENT,
}
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
NON_SLUG_CHAR_RE = re.compile(r"[^\w-]+", re.UNICODE)
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


def _entry_value(entry: object, key: str) -> object:
    getter = getattr(entry, "get", None)
    if callable(getter):
        return getter(key)
    return getattr(entry, key, None)


def _tag_terms(tags: object) -> list[str]:
    if not isinstance(tags, list):
        return []

    terms: list[str] = []
    for tag in tags:
        if isinstance(tag, Mapping):
            term = str(tag.get("term") or "").strip()
        else:
            term = str(getattr(tag, "term", "") or "").strip()
        if term:
            terms.append(term)
    return terms


def _clean_summary(summary: object) -> str | None:
    cleaned = html.unescape(str(summary or ""))
    cleaned = TAG_RE.sub(" ", cleaned)
    cleaned = _normalize_whitespace(cleaned)
    if not cleaned:
        return None
    return _truncate_on_word_boundary(cleaned, max_length=MAX_SNIPPET_LENGTH) or None


def _sanitize_source_token(value: str) -> str:
    slug = value.lower().strip()
    if not slug:
        return ""

    slug = re.sub(r"\s+", "-", slug)
    slug = slug.replace("_", "-")
    slug = NON_SLUG_CHAR_RE.sub("", slug)
    slug = MULTI_HYPHEN_RE.sub("-", slug).strip("-")
    return slug


def _source_channel(entry: object) -> str:
    tag_terms = _tag_terms(_entry_value(entry, "tags"))
    if not tag_terms:
        return "infoq_cn"

    category_slug = _sanitize_source_token(tag_terms[0])
    return f"infoq_cn:{category_slug}" if category_slug else "infoq_cn"


def _query_tokens(query_text: str) -> list[str]:
    tokens = [token.lower() for token in query_text.split() if token.strip()]
    if tokens:
        return tokens

    normalized = query_text.strip().lower()
    return [normalized] if normalized else []


def _item_matches_query(item: object, query_tokens: list[str]) -> bool:
    if not query_tokens:
        return True

    title = str(_entry_value(item, "title") or "")
    summary = str(_entry_value(item, "summary") or _entry_value(item, "description") or "")
    haystack = f"{title} {summary} {' '.join(_tag_terms(_entry_value(item, 'tags')))}".lower()
    return all(token in haystack for token in query_tokens)


def _to_evidence(entry: object, *, fetched_at: datetime) -> Evidence | None:
    url = str(_entry_value(entry, "link") or "").strip()
    if not url:
        return None

    title = _normalize_whitespace(html.unescape(str(_entry_value(entry, "title") or "").strip()))
    snippet = _clean_summary(_entry_value(entry, "summary") or _entry_value(entry, "description"))

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=snippet,
        source_channel=_source_channel(entry),
        fetched_at=fetched_at,
        score=0.0,
    )


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    try:
        if http_client is not None:
            response = await http_client.get(BASE_URL, headers=REQUEST_HEADERS)
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(BASE_URL, headers=REQUEST_HEADERS)

        response.raise_for_status()
        feed = await asyncio.to_thread(feedparser.parse, response.text)
    except Exception as exc:
        LOGGER.warning("infoq_cn_search_failed", reason=str(exc))
        return []

    if getattr(feed, "bozo", 0) == 1:
        reason = str(getattr(feed, "bozo_exception", None) or "failed to parse RSS feed")
        LOGGER.warning("infoq_cn_search_failed", reason=reason)
        return []

    query_tokens = _query_tokens(query.text)
    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for entry in getattr(feed, "entries", []):
        if not _item_matches_query(entry, query_tokens):
            continue

        evidence = _to_evidence(entry, fetched_at=fetched_at)
        if evidence is None:
            continue

        evidences.append(evidence)
        if len(evidences) >= MAX_RESULTS:
            break

    return evidences
