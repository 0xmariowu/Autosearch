from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.channels.base import PermanentError
from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError, to_channel_error

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="instagram")
SEARCH_PATH = "/api/v1/instagram/v2/general_search"
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
    code = str(item.get("code") or "").strip()
    if not code:
        return None

    url = f"https://www.instagram.com/p/{code}/"

    # Caption text
    cap = item.get("caption")
    cap_text = ""
    if isinstance(cap, Mapping):
        cap_text = _clean_text(cap.get("text"))
    elif isinstance(cap, str):
        cap_text = _clean_text(cap)

    # Author
    user_obj = item.get("user")
    username = ""
    if isinstance(user_obj, Mapping):
        username = str(user_obj.get("username") or "").strip()

    title = _truncate_on_word_boundary(cap_text, max_length=80) or "Instagram post"
    snippet = _truncate_on_word_boundary(cap_text, max_length=MAX_SNIPPET_LENGTH) or None

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=cap_text or snippet,
        source_channel=f"instagram:{username}" if username else "instagram:tikhub",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.get(SEARCH_PATH, {"keyword": query.text})
    except TikhubError as exc:
        # Bug 1 (fix-plan): translate TikHub error → channels.base typed
        # error so a 401/403/429/402 surfaces as auth_failed/rate_limited
        # at the MCP boundary instead of looking like an empty result.
        LOGGER.warning("instagram_tikhub_search_failed", reason=str(exc))
        raise to_channel_error(exc) from exc
    except ValueError as exc:
        # TikhubClient() raises ValueError on missing TIKHUB_API_KEY; the
        # MCP boundary already returns not_configured for that case via
        # SKILL.md requires, so this is a redundant safety net.
        LOGGER.warning("instagram_tikhub_search_failed", reason=str(exc))
        return []

    # payload.data.data.items
    outer = payload.get("data", {})
    inner = outer.get("data", {}) if isinstance(outer, Mapping) else {}
    items = inner.get("items", []) if isinstance(inner, Mapping) else []

    if not isinstance(items, list):
        LOGGER.warning("instagram_tikhub_search_failed", reason="invalid_payload_shape")
        raise PermanentError("instagram via_tikhub: invalid payload shape (schema drift?)")

    fetched_at = datetime.now(UTC)
    results: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        ev = _to_evidence(item, fetched_at=fetched_at)
        if ev is not None:
            results.append(ev)

    return results
