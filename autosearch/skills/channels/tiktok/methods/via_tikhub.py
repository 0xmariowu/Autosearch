from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.channels.base import PermanentError
from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError, to_channel_error

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="tiktok")
SEARCH_PATH = "/api/v1/tiktok/app/v3/fetch_general_search_result"
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


def _build_video_url(video: Mapping[str, object], *, unique_id: str, aweme_id: str) -> str:
    share_url = str(video.get("share_url") or "").strip()
    if share_url:
        return share_url
    if unique_id and aweme_id:
        return f"https://www.tiktok.com/@{unique_id}/video/{aweme_id}"
    return ""


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    aweme_info = item.get("aweme_info")
    if not isinstance(aweme_info, Mapping):
        return None

    author = aweme_info.get("author")
    author_map = author if isinstance(author, Mapping) else {}
    unique_id = str(author_map.get("unique_id") or "").strip()
    nickname = _clean_text(author_map.get("nickname"))
    aweme_id = str(aweme_info.get("aweme_id") or "").strip()
    url = _build_video_url(aweme_info, unique_id=unique_id, aweme_id=aweme_id)
    if not url:
        return None

    description = _clean_text(aweme_info.get("desc"))
    snippet = _truncate_on_word_boundary(description, max_length=MAX_SNIPPET_LENGTH) or None
    if nickname:
        title = f"@{nickname}"
    elif unique_id:
        title = f"@{unique_id}"
    else:
        title = "TikTok video"

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=description or snippet,
        source_channel="tiktok:tikhub",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.get(
            SEARCH_PATH,
            {
                "keyword": query.text,
                "offset": 0,
                "count": 20,
                "sort_type": 0,
                "publish_time": 0,
            },
        )
    except TikhubError as exc:
        # Bug 1 (fix-plan): translate TikHub error → channels.base typed
        # error so a 401/403/429/402 surfaces as auth_failed/rate_limited
        # at the MCP boundary instead of looking like an empty result.
        LOGGER.warning("tiktok_tikhub_search_failed", reason=str(exc))
        raise to_channel_error(exc) from exc
    except ValueError as exc:
        # TikhubClient() raises ValueError on missing TIKHUB_API_KEY; the
        # MCP boundary already returns not_configured for that case via
        # SKILL.md requires, so this is a redundant safety net.
        LOGGER.warning("tiktok_tikhub_search_failed", reason=str(exc))
        return []

    data = payload.get("data")
    items = data.get("data") if isinstance(data, Mapping) else None
    if not isinstance(items, list):
        LOGGER.warning("tiktok_tikhub_search_failed", reason="invalid_payload_shape")
        raise PermanentError("tiktok via_tikhub: invalid payload shape (schema drift?)")

    fetched_at = datetime.now(UTC)
    results: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            results.append(evidence)

    return results
