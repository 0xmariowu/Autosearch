from __future__ import annotations

import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.channels.base import PermanentError
from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError, to_channel_error

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="zhihu")
SEARCH_PATH = "/api/v1/zhihu/web/fetch_article_search_v3"
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _HTML_TAG_RE.sub("", text)
    return _normalize_whitespace(text)


def _build_article_url(article: Mapping[str, object]) -> str:
    raw_url = str(article.get("url") or "").strip()
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    if raw_url.startswith("/p/"):
        return f"https://zhuanlan.zhihu.com{raw_url}"
    if raw_url.startswith("/"):
        return f"https://www.zhihu.com{raw_url}"
    if raw_url:
        return f"https://zhuanlan.zhihu.com/p/{raw_url.lstrip('/')}"

    article_id = str(article.get("id") or "").strip()
    if article_id:
        return f"https://zhuanlan.zhihu.com/p/{article_id}"

    return ""


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    article = item.get("object")
    if not isinstance(article, Mapping):
        return None

    title = _clean_text(article.get("title"))
    snippet = _clean_text(article.get("excerpt")) or None
    content = (
        _clean_text(article.get("content"))
        or _clean_text(article.get("content_text"))
        or _clean_text(article.get("rich_text"))
        or snippet
    )
    url = _build_article_url(article)

    if not url:
        return None

    return Evidence(
        url=url,
        title=title or "Zhihu article",
        snippet=snippet,
        content=content,
        source_channel="zhihu:tikhub",
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
        LOGGER.warning("zhihu_tikhub_search_failed", reason=str(exc))
        raise to_channel_error(exc) from exc
    except ValueError as exc:
        # TikhubClient() raises ValueError on missing TIKHUB_API_KEY; the
        # MCP boundary already returns not_configured for that case via
        # SKILL.md requires, so this is a redundant safety net.
        LOGGER.warning("zhihu_tikhub_search_failed", reason=str(exc))
        return []

    data = payload.get("data", {})
    items = data.get("data", []) if isinstance(data, Mapping) else []
    if not isinstance(items, list):
        LOGGER.warning("zhihu_tikhub_search_failed", reason="invalid_payload_shape")
        raise PermanentError("zhihu via_tikhub: invalid payload shape (schema drift?)")

    fetched_at = datetime.now(UTC)
    results: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            results.append(evidence)

    return results
