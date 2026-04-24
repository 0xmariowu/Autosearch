from __future__ import annotations

import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError, to_channel_error

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="weibo")
SEARCH_PATH = "/api/v1/weibo/web/fetch_search"
MAX_SNIPPET_LENGTH = 300
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value: object) -> str:
    text = _HTML_TAG_RE.sub("", str(value or ""))
    return " ".join(html.unescape(text).split())


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


def _extract_mblogs(cards: object) -> list[Mapping[str, object]]:
    if not isinstance(cards, list):
        return []

    mblogs: list[Mapping[str, object]] = []
    for card in cards:
        if not isinstance(card, Mapping):
            continue

        card_type = card.get("card_type")
        if card_type == 9:
            mblog = card.get("mblog")
            if isinstance(mblog, Mapping):
                mblogs.append(mblog)
            continue

        if card_type == 11:
            mblogs.extend(_extract_mblogs(card.get("card_group")))

    return mblogs


def _build_post_url(item: Mapping[str, object]) -> str:
    user = item.get("user")
    user_map = user if isinstance(user, Mapping) else {}
    user_id = str(user_map.get("id") or "").strip()
    bid_or_mblogid = str(item.get("bid") or item.get("mblogid") or "").strip()
    if user_id and bid_or_mblogid:
        return f"https://weibo.com/{user_id}/{bid_or_mblogid}"

    mid = str(item.get("mid") or "").strip()
    if mid:
        return f"https://m.weibo.cn/detail/{mid}"

    return ""


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = _build_post_url(item)
    if not url:
        return None

    user = item.get("user")
    user_map = user if isinstance(user, Mapping) else {}
    screen_name = str(user_map.get("screen_name") or "").strip()
    content = _clean_text(item.get("text")) or None
    snippet = (
        _truncate_on_word_boundary(content, max_length=MAX_SNIPPET_LENGTH) if content else None
    )

    return Evidence(
        url=url,
        title=f"@{screen_name}" if screen_name else "Weibo post",
        snippet=snippet,
        content=content,
        source_channel="weibo:tikhub",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.get(
            SEARCH_PATH,
            {"keyword": query.text, "page": 1, "search_type": "1"},
        )
    except TikhubError as exc:
        # Bug 1 (fix-plan): translate TikHub error → channels.base typed
        # error so a 401/403/429/402 surfaces as auth_failed/rate_limited
        # at the MCP boundary instead of looking like an empty result.
        LOGGER.warning("weibo_tikhub_search_failed", reason=str(exc))
        raise to_channel_error(exc) from exc
    except ValueError as exc:
        # TikhubClient() raises ValueError on missing TIKHUB_API_KEY; the
        # MCP boundary already returns not_configured for that case via
        # SKILL.md requires, so this is a redundant safety net.
        LOGGER.warning("weibo_tikhub_search_failed", reason=str(exc))
        return []

    data = payload.get("data")
    nested_data = data.get("data") if isinstance(data, Mapping) else {}
    cards = nested_data.get("cards") if isinstance(nested_data, Mapping) else []
    if not isinstance(cards, list):
        LOGGER.warning("weibo_tikhub_search_failed", reason="invalid_payload_shape")
        return []

    fetched_at = datetime.now(UTC)
    results: list[Evidence] = []
    for mblog in _extract_mblogs(cards):
        evidence = _to_evidence(mblog, fetched_at=fetched_at)
        if evidence is not None:
            results.append(evidence)

    return results
