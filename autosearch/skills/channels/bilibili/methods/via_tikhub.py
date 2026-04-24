# Self-written for task F205
from __future__ import annotations

import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError, to_channel_error

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="bilibili")
SEARCH_PATH = "/api/v1/bilibili/web/fetch_general_search"
MAX_SNIPPET_LENGTH = 300
SUPPORTED_RESULT_TYPES = frozenset({"article", "video"})
HTML_TAG_RE = re.compile(r"<[^>]+>")
NON_SLUG_CHAR_RE = re.compile(r"[^\w-]+", re.UNICODE)
MULTI_HYPHEN_RE = re.compile(r"-+")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = HTML_TAG_RE.sub(" ", text)
    return _normalize_whitespace(text)


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


def _build_source_channel(result_type: str, author_name: str) -> str:
    base = f"bilibili:{result_type}"
    author_slug = _sanitize_source_token(author_name)
    return f"{base}:{author_slug}" if author_slug else base


def _extract_result_groups(
    payload: Mapping[str, object],
) -> list[tuple[str, list[Mapping[str, object]]]] | None:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return None

    nested_data = data.get("data")
    if not isinstance(nested_data, Mapping):
        return None

    result_list = nested_data.get("result")
    if not isinstance(result_list, list) or not result_list:
        return None

    # Detect format: old = items have {"result_type", "data"}, new = flat items with "type"
    first = result_list[0] if isinstance(result_list[0], Mapping) else {}
    is_grouped = "result_type" in first and "data" in first

    if is_grouped:
        # Old grouped format
        groups: list[tuple[str, list[Mapping[str, object]]]] = []
        for group in result_list:
            if not isinstance(group, Mapping):
                continue
            result_type = str(group.get("result_type") or "").strip().lower()
            if result_type not in SUPPORTED_RESULT_TYPES:
                continue
            items = group.get("data")
            if not isinstance(items, list):
                continue
            groups.append((result_type, [item for item in items if isinstance(item, Mapping)]))
        return groups or None
    else:
        # New flat format: each item in result_list is a direct evidence item
        flat: dict[str, list[Mapping[str, object]]] = {}
        for item in result_list:
            if not isinstance(item, Mapping):
                continue
            result_type = str(item.get("type") or item.get("result_type") or "").strip().lower()
            if result_type not in SUPPORTED_RESULT_TYPES:
                continue
            flat.setdefault(result_type, []).append(item)
        return [(rt, items) for rt, items in flat.items() if items] or None


def _build_video_url(item: Mapping[str, object]) -> str:
    raw_url = str(item.get("arcurl") or item.get("url") or "").strip()
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    if raw_url.startswith("//"):
        return f"https:{raw_url}"
    if raw_url.startswith("/"):
        return f"https://www.bilibili.com{raw_url}"

    bvid = str(item.get("bvid") or "").strip()
    if bvid:
        return f"https://www.bilibili.com/video/{bvid}"

    return ""


def _normalize_article_id(value: object) -> str:
    article_id = str(value or "").strip()
    if not article_id:
        return ""

    lowered = article_id.lower()
    if lowered.startswith("cv"):
        suffix = article_id[2:].strip()
        return f"cv{suffix}" if suffix else ""
    if article_id.isdigit():
        return f"cv{article_id}"
    return ""


def _build_article_url(item: Mapping[str, object]) -> str:
    for key in ("url", "arcurl", "uri", "jump_url"):
        raw_url = str(item.get(key) or "").strip()
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            return raw_url
        if raw_url.startswith("//"):
            return f"https:{raw_url}"
        if raw_url.startswith("/"):
            return f"https://www.bilibili.com{raw_url}"

        article_id = _normalize_article_id(raw_url)
        if article_id:
            return f"https://www.bilibili.com/read/{article_id}/"

    for key in ("id", "article_id", "cvid"):
        article_id = _normalize_article_id(item.get(key))
        if article_id:
            return f"https://www.bilibili.com/read/{article_id}/"

    return ""


def _to_video_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = _build_video_url(item)
    if not url:
        return None

    title = _clean_text(item.get("title")) or "Bilibili video"
    description = _clean_text(item.get("description"))
    snippet = _truncate_on_word_boundary(description, max_length=MAX_SNIPPET_LENGTH) or None
    author_name = _clean_text(item.get("author"))

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=description or snippet,
        source_channel=_build_source_channel("video", author_name),
        fetched_at=fetched_at,
    )


def _to_article_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = _build_article_url(item)
    if not url:
        return None

    title = _clean_text(item.get("title")) or "Bilibili article"
    summary = _clean_text(item.get("summary") or item.get("description") or item.get("desc"))
    content = _clean_text(item.get("content")) or summary
    snippet = _truncate_on_word_boundary(summary or content, max_length=MAX_SNIPPET_LENGTH) or None
    author_name = _clean_text(item.get("author_name") or item.get("author") or item.get("uname"))

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=content or snippet,
        source_channel=_build_source_channel("article", author_name),
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.get(
            SEARCH_PATH,
            {
                "keyword": query.text,
                "search_type": "video",
                "order": "totalrank",
                "page": 1,
                "page_size": 10,
            },
        )
    except TikhubError as exc:
        # Bug 1 (fix-plan): translate TikHub error → channels.base typed
        # error so a 401/403/429/402 surfaces as auth_failed/rate_limited
        # at the MCP boundary instead of looking like an empty result.
        LOGGER.warning("bilibili_tikhub_search_failed", reason=str(exc))
        raise to_channel_error(exc) from exc
    except ValueError as exc:
        # TikhubClient() raises ValueError on missing TIKHUB_API_KEY; the
        # MCP boundary already returns not_configured for that case via
        # SKILL.md requires, so this is a redundant safety net.
        LOGGER.warning("bilibili_tikhub_search_failed", reason=str(exc))
        return []

    result_groups = _extract_result_groups(payload)
    if result_groups is None:
        LOGGER.warning("bilibili_tikhub_search_failed", reason="invalid_payload_shape")
        return []

    fetched_at = datetime.now(UTC)
    results: list[Evidence] = []
    for result_type, items in result_groups:
        for item in items:
            evidence = (
                _to_video_evidence(item, fetched_at=fetched_at)
                if result_type == "video"
                else _to_article_evidence(item, fetched_at=fetched_at)
            )
            if evidence is not None:
                results.append(evidence)

    return results
