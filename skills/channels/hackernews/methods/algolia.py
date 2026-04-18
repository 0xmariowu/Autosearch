# Self-written, plan autosearch-0418-channels-and-skills.md § F003
import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="hackernews")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
BASE_URL = "https://hn.algolia.com/api/v1/search"


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _HTML_TAG_RE.sub("", text)
    return _normalize_whitespace(text)


def _truncate_with_ellipsis(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


async def search(query: SubQuery) -> list[Evidence]:
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(
                BASE_URL,
                params={
                    "query": query.text,
                    "hitsPerPage": MAX_RESULTS,
                    "tags": "(story,comment)",
                },
            )
            response.raise_for_status()

        payload = response.json()
        hits = payload.get("hits", [])
        if not isinstance(hits, list):
            raise ValueError("invalid hits payload")
    except Exception as exc:
        LOGGER.warning("hackernews_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    return [_to_evidence(hit, fetched_at=fetched_at) for hit in hits if isinstance(hit, Mapping)]


def _to_evidence(hit: Mapping[str, object], *, fetched_at: datetime) -> Evidence:
    object_id = str(hit.get("objectID") or "").strip()
    internal_url = _item_url(object_id)
    external_url = str(hit.get("url") or "").strip()
    title = _clean_text(hit.get("title"))
    story_text = _clean_text(hit.get("story_text"))
    comment_text = _clean_text(hit.get("comment_text"))
    snippet = (story_text or comment_text)[:500] or None
    fallback_title = comment_text or story_text or f"Hacker News item {object_id}".strip()

    return Evidence(
        url=external_url or internal_url,
        title=title or _truncate_with_ellipsis(fallback_title, 80),
        snippet=snippet,
        source_channel="hackernews",
        fetched_at=fetched_at,
        score=0.0,
    )


def _item_url(object_id: str) -> str:
    if object_id:
        return f"https://news.ycombinator.com/item?id={object_id}"
    return "https://news.ycombinator.com/"
