# Self-written for task F205
from __future__ import annotations

import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError, to_channel_error

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="douyin")
SEARCH_PATH = "/api/v1/douyin/search/fetch_general_search_v1"
MAX_TITLE_LENGTH = 80
MAX_SNIPPET_LENGTH = 300
NON_SLUG_CHAR_RE = re.compile(r"[^\w-]+", re.UNICODE)
MULTI_HYPHEN_RE = re.compile(r"-+")


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


def _sanitize_source_token(value: str) -> str:
    slug = value.lower().strip()
    if not slug:
        return ""

    slug = re.sub(r"\s+", "-", slug)
    slug = slug.replace("_", "-")
    slug = NON_SLUG_CHAR_RE.sub("", slug)
    slug = MULTI_HYPHEN_RE.sub("-", slug).strip("-")
    return slug


def _build_source_channel(nickname: str) -> str:
    nickname_slug = _sanitize_source_token(nickname)
    return f"douyin:{nickname_slug}" if nickname_slug else "douyin"


def _build_video_url(video: Mapping[str, object]) -> str:
    share_url = str(video.get("share_url") or "").strip()
    if share_url:
        return share_url

    aweme_id = str(video.get("aweme_id") or "").strip()
    if aweme_id:
        return f"https://www.douyin.com/video/{aweme_id}"

    return ""


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    aweme_info = item.get("aweme_info")
    if not isinstance(aweme_info, Mapping):
        return None

    aweme_id = str(aweme_info.get("aweme_id") or "").strip()
    url = _build_video_url(aweme_info)
    if not url:
        return None

    description = _clean_text(aweme_info.get("desc"))
    title = _truncate_on_word_boundary(description, max_length=MAX_TITLE_LENGTH)
    if not title:
        title = f"Douyin video {aweme_id}" if aweme_id else "Douyin video"

    snippet = _truncate_on_word_boundary(description, max_length=MAX_SNIPPET_LENGTH) or None
    author = aweme_info.get("author")
    author_map = author if isinstance(author, Mapping) else {}
    nickname = _clean_text(author_map.get("nickname"))

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=description or snippet,
        source_channel=_build_source_channel(nickname),
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.post(
            SEARCH_PATH,
            {"keyword": query.text, "cursor": 0, "sort_type": "0"},
        )
    except TikhubError as exc:
        # Bug 1 (fix-plan): translate TikHub error → channels.base typed
        # error so a 401/403/429/402 surfaces as auth_failed/rate_limited
        # at the MCP boundary instead of looking like an empty result.
        LOGGER.warning("douyin_tikhub_search_failed", reason=str(exc))
        raise to_channel_error(exc) from exc
    except ValueError as exc:
        # TikhubClient() raises ValueError on missing TIKHUB_API_KEY; the
        # MCP boundary already returns not_configured for that case via
        # SKILL.md requires, so this is a redundant safety net.
        LOGGER.warning("douyin_tikhub_search_failed", reason=str(exc))
        return []

    data = payload.get("data")
    items = data.get("data") if isinstance(data, Mapping) else None
    if not isinstance(items, list):
        LOGGER.warning("douyin_tikhub_search_failed", reason="invalid_payload_shape")
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
