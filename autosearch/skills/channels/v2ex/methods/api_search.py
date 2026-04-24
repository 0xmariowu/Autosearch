from __future__ import annotations

import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="v2ex")

BASE_URL = "https://www.sov2ex.com/api/search"
HTTP_TIMEOUT = 15.0
MAX_RESULTS = 10
MAX_SNIPPET_LENGTH = 300
TITLE_FALLBACK_LENGTH = 60
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def _normalize_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def _clean_text(value: object) -> str:
    text = HTML_TAG_RE.sub(" ", str(value or ""))
    return _normalize_whitespace(html.unescape(text))


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


def _fallback_title(content: str | None) -> str:
    if not content:
        return ""

    excerpt = content[:TITLE_FALLBACK_LENGTH].strip()
    if not excerpt:
        return ""
    if len(content) > TITLE_FALLBACK_LENGTH:
        return f"{excerpt}…"
    return excerpt


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    thread_id = str(item.get("id") or "").strip()
    if not thread_id:
        return None

    content = _clean_text(item.get("content")) or None
    title = _clean_text(item.get("title")) or _fallback_title(content) or "V2EX thread"
    snippet = (
        _truncate_on_word_boundary(content, max_length=MAX_SNIPPET_LENGTH) if content else None
    )

    return Evidence(
        url=f"https://www.v2ex.com/t/{thread_id}",
        title=title,
        snippet=snippet,
        content=content,
        source_channel="v2ex",
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
            response = await http_client.get(
                BASE_URL,
                params={"q": query.text, "size": MAX_RESULTS},
            )
        else:
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    BASE_URL,
                    params={"q": query.text, "size": MAX_RESULTS},
                )

        response.raise_for_status()
        payload = response.json()
        hits = payload.get("hits")
        if not isinstance(hits, list):
            raise ValueError("invalid hits payload")
    except Exception as exc:
        LOGGER.warning("v2ex_search_failed", reason=str(exc))
        raise_as_channel_error(exc)

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for hit in hits:
        if not isinstance(hit, Mapping):
            continue

        source = hit.get("_source")
        if not isinstance(source, Mapping):
            continue

        evidence = _to_evidence(source, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
