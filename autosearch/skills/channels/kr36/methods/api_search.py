# Self-written for task F204
from __future__ import annotations

import asyncio
import html
import re
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.html_scraper import HtmlFetchError, fetch_html, fetch_page

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="kr36")

BASE_URL = "https://www.36kr.com/search"
MAX_RESULTS = 10
MAX_SNIPPET_LENGTH = 300
TITLE_LINK_RE = re.compile(
    r'<a\b(?=[^>]*class=(["\'])[^"\']*\barticle-item-title\b[^"\']*\1)'
    r'(?=[^>]*href=(?P<quote>["\'])(?P<href>.*?)(?P=quote))[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
DESCRIPTION_RE = re.compile(
    r'<div\b(?=[^>]*class=(["\'])[^"\']*\barticle-item-description\b[^"\']*\1)[^>]*>'
    r"(?P<description>.*?)</div>",
    re.IGNORECASE | re.DOTALL,
)
AUTHOR_RE = re.compile(
    r'<span\b(?=[^>]*class=(["\'])[^"\']*\barticle-author\b[^"\']*\1)[^>]*>'
    r"(?P<author>.*?)</span>",
    re.IGNORECASE | re.DOTALL,
)
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


def _clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = TAG_RE.sub(" ", text)
    return _normalize_whitespace(text)


def _sanitize_source_token(value: str) -> str:
    slug = value.lower().strip()
    if not slug:
        return ""

    slug = re.sub(r"\s+", "-", slug)
    slug = slug.replace("_", "-")
    slug = NON_SLUG_CHAR_RE.sub("", slug)
    slug = MULTI_HYPHEN_RE.sub("-", slug).strip("-")
    return slug


def _build_source_channel(author_name: str) -> str:
    author_slug = _sanitize_source_token(author_name)
    return f"kr36:{author_slug}" if author_slug else "kr36"


def _resolve_url(href: str) -> str | None:
    cleaned = html.unescape(href).strip()
    if not cleaned:
        return None
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    if cleaned.startswith("/"):
        return f"https://www.36kr.com{cleaned}"
    return cleaned


def _to_evidence(
    segment: str, title_match: re.Match[str], *, fetched_at: datetime
) -> Evidence | None:
    url = _resolve_url(title_match.group("href"))
    title = _clean_text(title_match.group("title"))
    if not url or not title:
        return None

    description_match = DESCRIPTION_RE.search(segment)
    description_text = (
        _clean_text(description_match.group("description")) if description_match else ""
    )
    snippet = _truncate_on_word_boundary(description_text, max_length=MAX_SNIPPET_LENGTH) or None

    author_match = AUTHOR_RE.search(segment)
    author_name = _clean_text(author_match.group("author")) if author_match else ""

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=snippet,
        source_channel=_build_source_channel(author_name),
        fetched_at=fetched_at,
        score=0.0,
    )


def _parse_results(html_text: str, *, fetched_at: datetime) -> list[Evidence]:
    matches = list(TITLE_LINK_RE.finditer(html_text))
    evidences: list[Evidence] = []
    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(html_text)
        segment = html_text[match.start() : next_start]
        evidence = _to_evidence(segment, match, fetched_at=fetched_at)
        if evidence is None:
            continue
        evidences.append(evidence)
        if len(evidences) >= MAX_RESULTS:
            break
    return evidences


async def _enrich_evidence(
    evidence: Evidence,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> Evidence:
    try:
        page = await fetch_page(evidence.url, client=http_client)
    except HtmlFetchError as exc:
        LOGGER.warning(
            "kr36_result_fetch_failed",
            url=evidence.url,
            reason=str(exc),
        )
        return evidence
    except Exception as exc:
        LOGGER.warning(
            "kr36_result_fetch_failed",
            url=evidence.url,
            reason=str(exc),
        )
        return evidence

    return evidence.model_copy(
        update={
            "snippet": page.markdown[:MAX_SNIPPET_LENGTH],
            "content": page.markdown,
            "source_page": page,
        }
    )


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    try:
        html_text = await fetch_html(
            BASE_URL,
            http_client=http_client,
            params={"searchType": "post", "q": query.text},
        )
        evidences = await asyncio.to_thread(
            _parse_results,
            html_text,
            fetched_at=datetime.now(UTC),
        )
    except HtmlFetchError as exc:
        LOGGER.warning("kr36_search_failed", reason=str(exc))
        raise_as_channel_error(exc)
    except Exception as exc:
        LOGGER.warning("kr36_search_failed", reason=str(exc))
        raise_as_channel_error(exc)

    return await asyncio.gather(
        *[_enrich_evidence(evidence, http_client=http_client) for evidence in evidences]
    )
