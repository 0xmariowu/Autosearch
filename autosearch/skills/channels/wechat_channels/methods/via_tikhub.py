from __future__ import annotations

import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.channels.base import PermanentError
from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError, to_channel_error

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="wechat_channels")
SEARCH_PATH = "/api/v1/wechat_channels/fetch_search_latest"
_HTML_TAG_RE = re.compile(r"<[^>]+>")
MAX_SNIPPET_LENGTH = 300


def _clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _HTML_TAG_RE.sub("", text)
    return " ".join(text.split())


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
    video_url = str(item.get("videoUrl") or "").strip()
    doc_id = str(item.get("docID") or item.get("hashDocID") or "").strip()

    if not video_url and not doc_id:
        return None

    # Use videoUrl as the primary identifier; fall back to docID-based URL
    url = video_url if video_url else f"https://channels.weixin.qq.com/video/{doc_id}"

    title = _clean_text(item.get("title"))

    # Creator info from source dict
    source = item.get("source")
    creator = ""
    if isinstance(source, Mapping):
        creator = _clean_text(source.get("title"))

    # Duration as extra context
    duration = str(item.get("duration") or "").strip()
    snippet_parts = []
    if creator:
        snippet_parts.append(f"Creator: {creator}")
    if duration:
        snippet_parts.append(f"Duration: {duration}")
    snippet = " | ".join(snippet_parts) or None

    title_text = _truncate_on_word_boundary(title, max_length=80) or "WeChat Channels video"

    return Evidence(
        url=url,
        title=title_text,
        snippet=snippet,
        content=title or snippet,
        source_channel=f"wechat_channels:{creator}" if creator else "wechat_channels:tikhub",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.get(
            SEARCH_PATH,
            {"keywords": query.text, "count": 12},
        )
    except TikhubError as exc:
        # Bug 1 (fix-plan): translate TikHub error → channels.base typed
        # error so a 401/403/429/402 surfaces as auth_failed/rate_limited
        # at the MCP boundary instead of looking like an empty result.
        LOGGER.warning("wechat_channels_tikhub_search_failed", reason=str(exc))
        raise to_channel_error(exc) from exc
    except ValueError as exc:
        # TikhubClient() raises ValueError on missing TIKHUB_API_KEY; the
        # MCP boundary already returns not_configured for that case via
        # SKILL.md requires, so this is a redundant safety net.
        LOGGER.warning("wechat_channels_tikhub_search_failed", reason=str(exc))
        return []

    # Navigate to video items
    data = payload.get("data", {})
    if not isinstance(data, Mapping):
        LOGGER.warning("wechat_channels_tikhub_search_failed", reason="invalid_payload_shape")
        raise PermanentError("wechat_channels via_tikhub: invalid payload shape (schema drift?)")

    items: list[Mapping[str, object]] = []

    def _find_items(obj: object, depth: int = 0) -> None:
        if depth > 5:
            return
        if isinstance(obj, list):
            for x in obj:
                if isinstance(x, Mapping) and "docID" in x:
                    items.append(x)
                _find_items(x, depth + 1)
        elif isinstance(obj, Mapping):
            for v in obj.values():
                _find_items(v, depth + 1)

    _find_items(data)

    if not items:
        LOGGER.warning("wechat_channels_tikhub_search_failed", reason="no_items_in_response")
        # NOTE: ambiguous path — if TikHub renamed the docID key this would
        # be schema drift (should raise PermanentError), but it's also the
        # legit "search found zero results" result. Leaving as [] until we
        # see concrete drift reports.
        return []

    fetched_at = datetime.now(UTC)
    results: list[Evidence] = []
    for item in items:
        ev = _to_evidence(item, fetched_at=fetched_at)
        if ev is not None:
            results.append(ev)

    return results
