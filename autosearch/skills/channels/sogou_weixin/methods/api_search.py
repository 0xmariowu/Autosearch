# Self-written for task F204
from __future__ import annotations

import asyncio
import html
import re
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.html_scraper import HtmlFetchError, fetch_html, fetch_page

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="sogou_weixin")

BASE_URL = "https://weixin.sogou.com/weixin"
MAX_RESULTS = 10
MAX_SNIPPET_LENGTH = 300
RESULT_BLOCK_RE = re.compile(
    r'<li\b[^>]*id=["\']sogou_vr_[^"\']+["\'][^>]*>.*?</li>',
    re.IGNORECASE | re.DOTALL,
)
TITLE_LINK_RE = re.compile(
    r'<h3\b[^>]*>\s*<a\b[^>]*href=(?P<quote>["\'])(?P<href>.*?)(?P=quote)[^>]*>'
    r"(?P<title>.*?)</a>\s*</h3>",
    re.IGNORECASE | re.DOTALL,
)
SNIPPET_RE = re.compile(
    r'<p\b(?=[^>]*class=(["\'])[^"\']*\btxt-info\b[^"\']*\1)[^>]*>'
    r"(?P<snippet>.*?)</p>",
    re.IGNORECASE | re.DOTALL,
)
ACCOUNT_RE = re.compile(
    r'<a\b(?=[^>]*class=(["\'])[^"\']*\baccount\b[^"\']*\1)[^>]*>'
    r"(?P<account>.*?)</a>",
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


def _build_source_channel(account_name: str) -> str:
    account_slug = _sanitize_source_token(account_name)
    return f"sogou_weixin:{account_slug}" if account_slug else "sogou_weixin"


def _resolve_url(href: str) -> str | None:
    cleaned = html.unescape(href).strip()
    if not cleaned:
        return None
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    if cleaned.startswith("/"):
        return f"https://weixin.sogou.com{cleaned}"
    return cleaned


def _to_evidence(block: str, *, fetched_at: datetime) -> Evidence | None:
    title_match = TITLE_LINK_RE.search(block)
    if title_match is None:
        return None

    url = _resolve_url(title_match.group("href"))
    title = _clean_text(title_match.group("title"))
    if not url or not title:
        return None

    snippet_match = SNIPPET_RE.search(block)
    snippet_text = _clean_text(snippet_match.group("snippet")) if snippet_match else ""
    snippet = _truncate_on_word_boundary(snippet_text, max_length=MAX_SNIPPET_LENGTH) or None

    account_match = ACCOUNT_RE.search(block)
    account_name = _clean_text(account_match.group("account")) if account_match else ""

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=snippet,
        source_channel=_build_source_channel(account_name),
        fetched_at=fetched_at,
        score=0.0,
    )


def _parse_results(html_text: str, *, fetched_at: datetime) -> list[Evidence]:
    evidences: list[Evidence] = []
    for match in RESULT_BLOCK_RE.finditer(html_text):
        evidence = _to_evidence(match.group(0), fetched_at=fetched_at)
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
            "sogou_weixin_result_fetch_failed",
            url=evidence.url,
            reason=str(exc),
        )
        return evidence
    except Exception as exc:
        LOGGER.warning(
            "sogou_weixin_result_fetch_failed",
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
            params={"type": "2", "query": query.text},
        )
        evidences = await asyncio.to_thread(
            _parse_results,
            html_text,
            fetched_at=datetime.now(UTC),
        )
    except HtmlFetchError as exc:
        LOGGER.warning("sogou_weixin_search_failed", reason=str(exc))
        return []
    except Exception as exc:
        LOGGER.warning("sogou_weixin_search_failed", reason=str(exc))
        return []

    return await asyncio.gather(
        *[_enrich_evidence(evidence, http_client=http_client) for evidence in evidences]
    )
