from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="xiaohongshu")
SEARCH_PATH = "/api/v1/xiaohongshu/web/search_notes"
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


def _build_note_url(item: Mapping[str, object]) -> str:
    share_info = item.get("share_info")
    if isinstance(share_info, Mapping):
        link = str(share_info.get("link") or "").strip()
        if link:
            return link

    note_id = str(item.get("id") or "").strip()
    if note_id:
        return f"https://www.xiaohongshu.com/explore/{note_id}"

    return ""


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = _build_note_url(item)
    if not url:
        return None

    title = _clean_text(item.get("title"))
    description = _clean_text(item.get("desc"))
    snippet = _truncate_on_word_boundary(description, max_length=MAX_SNIPPET_LENGTH) or None
    content = description or snippet

    return Evidence(
        url=url,
        title=title or "Xiaohongshu note",
        snippet=snippet,
        content=content,
        source_channel="xiaohongshu:tikhub",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.get(SEARCH_PATH, {"keyword": query.text})
    except (TikhubError, ValueError) as exc:
        LOGGER.warning("xiaohongshu_tikhub_search_failed", reason=str(exc))
        return []

    data = payload.get("data", {})
    items = data.get("items", []) if isinstance(data, Mapping) else []
    if not isinstance(items, list):
        LOGGER.warning("xiaohongshu_tikhub_search_failed", reason="invalid_payload_shape")
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
