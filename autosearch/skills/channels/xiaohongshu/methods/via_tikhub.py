from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError, to_channel_error

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="xiaohongshu")

SEARCH_PATH = "/api/v1/xiaohongshu/web_v3/fetch_search_notes"

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
    note_id = str(item.get("id") or "").strip()
    if not note_id:
        return ""
    xsec = str(item.get("xsecToken") or "").strip()
    if xsec:
        return (
            f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec}&xsec_source=pc_search"
        )
    return f"https://www.xiaohongshu.com/explore/{note_id}"


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = _build_note_url(item)
    if not url:
        return None

    # noteCard holds the actual content
    note_card = item.get("noteCard")
    if isinstance(note_card, Mapping):
        title = _clean_text(note_card.get("displayTitle") or note_card.get("title"))
        user = note_card.get("user") or {}
        author = _clean_text(user.get("nickname") if isinstance(user, Mapping) else None)
        desc = _clean_text(note_card.get("desc"))
    else:
        title = _clean_text(item.get("title") or item.get("display_title"))
        author = ""
        desc = _clean_text(item.get("desc"))

    snippet = _truncate_on_word_boundary(desc, max_length=MAX_SNIPPET_LENGTH) or None
    content = desc or snippet

    return Evidence(
        url=url,
        title=title or author or "Xiaohongshu note",
        snippet=snippet,
        content=content,
        source_channel="xiaohongshu:tikhub",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    tikhub_client = client or TikhubClient()

    # TikHub web_v3 handles XHS signing internally — direct GET, no sign step needed.
    try:
        payload = await tikhub_client.get(
            SEARCH_PATH,
            {"keyword": query.text, "page": 1, "page_size": 20, "sort": "general", "note_type": 0},
        )
    except TikhubError as exc:
        # Bug 1 (fix-plan): translate TikHub error → channels.base typed
        # error so a 401/403/429/402 surfaces as auth_failed/rate_limited
        # at the MCP boundary instead of looking like an empty result.
        LOGGER.warning("xiaohongshu_tikhub_search_failed", reason=str(exc))
        raise to_channel_error(exc) from exc
    except ValueError as exc:
        # TikhubClient() raises ValueError on missing TIKHUB_API_KEY; the
        # MCP boundary already returns not_configured for that case via
        # SKILL.md requires, so this is a redundant safety net.
        LOGGER.warning("xiaohongshu_tikhub_search_failed", reason=str(exc))
        return []

    # Navigate: payload.data.data.items
    outer = payload.get("data", {})
    inner = outer.get("data", {}) if isinstance(outer, Mapping) else {}
    items = inner.get("items", []) if isinstance(inner, Mapping) else []

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
