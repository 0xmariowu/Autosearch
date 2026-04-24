# Self-written, plan autosearch-0418-channels-and-skills.md § F003
import html
import os
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="youtube")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
BASE_URL = "https://www.googleapis.com/youtube/v3/search"
_WARNED_NO_API_KEY = False


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _clean_text(value: object) -> str:
    return _normalize_whitespace(html.unescape(str(value or "")))


async def search(query: SubQuery) -> list[Evidence]:
    global _WARNED_NO_API_KEY

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        if not _WARNED_NO_API_KEY:
            LOGGER.warning("youtube_search_skipped", reason="no_api_key")
            _WARNED_NO_API_KEY = True
        return []

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(
                BASE_URL,
                params={
                    "part": "snippet",
                    "q": query.text,
                    "type": "video",
                    "maxResults": MAX_RESULTS,
                },
                headers={"x-goog-api-key": api_key},
            )
            response.raise_for_status()

        payload = response.json()
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise ValueError("invalid items payload")
        fetched_at = datetime.now(UTC)
        return [
            _to_evidence(item, fetched_at=fetched_at) for item in items if isinstance(item, Mapping)
        ]
    except httpx.HTTPStatusError as exc:
        reason = "auth_failed" if exc.response.status_code in {401, 403} else str(exc)
        LOGGER.warning("youtube_search_failed", reason=reason)
        return []
    except Exception as exc:
        LOGGER.warning("youtube_search_failed", reason=str(exc))
        raise_as_channel_error(exc)


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence:
    item_id = item["id"]
    snippet = item["snippet"]
    if not isinstance(item_id, Mapping) or not isinstance(snippet, Mapping):
        raise ValueError("invalid youtube item")

    video_id = str(item_id["videoId"]).strip()
    title = _clean_text(snippet["title"])
    description = _clean_text(snippet.get("description"))

    return Evidence(
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=title,
        snippet=description[:500] or None,
        source_channel="youtube",
        fetched_at=fetched_at,
        score=0.0,
    )
