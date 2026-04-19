from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="kuaishou")
SEARCH_PATH = "/api/v1/kuaishou/app/search_comprehensive"
MAX_SNIPPET_LENGTH = 300


def _clean_text(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


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


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    feed = item.get("feed")
    if not isinstance(feed, Mapping):
        return None

    photo_id = str(feed.get("photo_id") or "").strip()
    if not photo_id:
        return None

    caption = _clean_text(feed.get("caption"))
    snippet = _truncate_on_word_boundary(caption, max_length=MAX_SNIPPET_LENGTH) or None
    user_name = _clean_text(feed.get("user_name"))
    title = f"@{user_name}" if user_name else "Kuaishou video"

    return Evidence(
        url=f"https://www.kuaishou.com/short-video/{photo_id}",
        title=title,
        snippet=snippet,
        content=caption or snippet,
        source_channel="kuaishou:tikhub",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.get(
            SEARCH_PATH,
            {
                "keyword": query.text,
                "sort_type": "all",
                "publish_time": "all",
                "duration": "all",
                "search_scope": "all",
            },
        )
    except (TikhubError, ValueError) as exc:
        LOGGER.warning("kuaishou_tikhub_search_failed", reason=str(exc))
        return []

    data = payload.get("data")
    items = data.get("mixFeeds") if isinstance(data, Mapping) else None
    if not isinstance(items, list):
        LOGGER.warning("kuaishou_tikhub_search_failed", reason="invalid_payload_shape")
        return []

    fetched_at = datetime.now(UTC)
    results: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            results.append(evidence)

    return results
