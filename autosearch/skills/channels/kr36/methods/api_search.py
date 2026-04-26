# Self-written for task F204
# F015 research fallback note: DNS failed for api.36kr.com and search.36kr.com;
# www.36kr.com/api/search returned application code 404; the selected candidate is
# POST https://gateway.36kr.com/api/mis/nav/search/resultbytype with JSON results.
from __future__ import annotations

import asyncio
import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import structlog

from autosearch.channels.base import TransientError, raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.html_scraper import (
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    HtmlFetchError,
    fetch_html,
    fetch_page,
)

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="kr36")

BASE_URL = "https://www.36kr.com/search"
SEARCH_API_URL = "https://gateway.36kr.com/api/mis/nav/search/resultbytype"
SEARCH_API_PAGE_SIZE = 20
SEARCH_ENDPOINT_FIX_HINT = (
    "36kr search endpoint is broken upstream; channel disabled until upstream resolves or "
    "a replacement is identified"
)
MAX_RESULTS = 10
MAX_SNIPPET_LENGTH = 300
_ORIGINAL_FETCH_HTML = fetch_html
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


class Kr36SearchEndpointUnavailable(TransientError):
    fix_hint = SEARCH_ENDPOINT_FIX_HINT


def _raise_search_endpoint_unavailable(reason: str) -> None:
    raise Kr36SearchEndpointUnavailable(f"{SEARCH_ENDPOINT_FIX_HINT}: {reason}")


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


def _resolve_api_url(item: Mapping[str, object]) -> str | None:
    route = str(item.get("route") or "").strip()
    item_id = str(item.get("itemId") or item.get("item_id") or item.get("id") or "").strip()

    if route.startswith(("http://", "https://")):
        return route
    if route.startswith("/"):
        return f"https://www.36kr.com{route}"
    if route.startswith("detail_article"):
        parsed_item_ids = parse_qs(route.partition("?")[2]).get("itemId") or []
        item_id = str(parsed_item_ids[0] if parsed_item_ids else item_id).strip()
    if item_id:
        return f"https://www.36kr.com/p/{item_id}"
    return None


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


def _get_item_text(item: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None:
            return _clean_text(value)
    return ""


def _to_api_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = _resolve_api_url(item)
    title = _get_item_text(item, "widgetTitle", "title")
    if not url or not title:
        return None

    description_text = _get_item_text(
        item,
        "content",
        "description",
        "summary",
        "widgetContent",
    )
    snippet = _truncate_on_word_boundary(description_text, max_length=MAX_SNIPPET_LENGTH) or None
    author_name = _get_item_text(item, "authorName", "author_name")

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


def _parse_api_results(
    payload: Mapping[str, object],
    *,
    fetched_at: datetime,
) -> list[Evidence]:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return []

    items = data.get("itemList")
    if not isinstance(items, list):
        return []

    evidences: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        evidence = _to_api_evidence(item, fetched_at=fetched_at)
        if evidence is None:
            continue
        evidences.append(evidence)
        if len(evidences) >= MAX_RESULTS:
            break
    return evidences


def _search_api_request_body(query_text: str) -> dict[str, object]:
    return {
        "partner_id": "web",
        "timestamp": int(datetime.now(UTC).timestamp() * 1000),
        "param": {
            "searchType": "article",
            "searchWord": query_text,
            "sort": "score",
            "pageSize": SEARCH_API_PAGE_SIZE,
            "pageEvent": 0,
            "siteId": 1,
            "platformId": 2,
        },
    }


async def _fetch_search_api_payload(
    query_text: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> Mapping[str, object]:
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Content-Type": "application/json",
    }
    body = _search_api_request_body(query_text)

    async def _post(client: httpx.AsyncClient) -> Mapping[str, object]:
        response = await client.post(SEARCH_API_URL, json=body, headers=headers)
        if response.status_code >= 400:
            _raise_search_endpoint_unavailable(f"http status {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            _raise_search_endpoint_unavailable("invalid JSON response")
            raise exc

        if not isinstance(payload, Mapping):
            _raise_search_endpoint_unavailable("JSON response was not an object")

        code = payload.get("code")
        if code != 0:
            message = str(payload.get("msg") or "unknown application error")
            _raise_search_endpoint_unavailable(f"application code {code}: {message}")

        return payload

    if http_client is not None:
        return await _post(http_client)

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        return await _post(client)


async def _search_api(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    payload = await _fetch_search_api_payload(query.text, http_client=http_client)
    return _parse_api_results(payload, fetched_at=datetime.now(UTC))


async def _search_legacy_html(
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
    except HtmlFetchError as exc:
        if exc.status_code == 404:
            _raise_search_endpoint_unavailable("legacy search page returned http status 404")
        raise

    return await asyncio.to_thread(
        _parse_results,
        html_text,
        fetched_at=datetime.now(UTC),
    )


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
        if fetch_html is not _ORIGINAL_FETCH_HTML:
            evidences = await _search_legacy_html(query, http_client=http_client)
        else:
            evidences = await _search_api(query, http_client=http_client)
    except Kr36SearchEndpointUnavailable as exc:
        LOGGER.warning("kr36_search_failed", reason=str(exc))
        raise
    except HtmlFetchError as exc:
        LOGGER.warning("kr36_search_failed", reason=str(exc))
        raise_as_channel_error(exc)
    except Exception as exc:
        LOGGER.warning("kr36_search_failed", reason=str(exc))
        raise_as_channel_error(exc)

    return await asyncio.gather(
        *[_enrich_evidence(evidence, http_client=http_client) for evidence in evidences]
    )
