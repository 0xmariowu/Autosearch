"""SearXNG meta-search channel — requires SEARXNG_URL env var."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import MethodUnavailable
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="searxng")

_HTTP_TIMEOUT = 15.0
_MAX_RESULTS = 10


async def search(query: SubQuery) -> list[Evidence]:
    base_url = os.environ.get("SEARXNG_URL", "").rstrip("/")
    if not base_url:
        raise MethodUnavailable("SEARXNG_URL is not set")

    try:
        return await _do_search(base_url, query.text)
    except MethodUnavailable:
        raise
    except Exception as exc:
        LOGGER.warning("searxng_search_failed", reason=str(exc))
        return []


async def _do_search(base_url: str, query: str) -> list[Evidence]:
    params = {"q": query, "format": "json", "language": "auto"}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(f"{base_url}/search", params=params)
        resp.raise_for_status()
    data = resp.json()
    results = (data.get("results") or [])[:_MAX_RESULTS]
    fetched_at = datetime.now(UTC)
    return [_to_evidence(r, fetched_at) for r in results if r.get("url")]


def _to_evidence(item: dict, fetched_at: datetime) -> Evidence:
    engine = item.get("engine") or ""
    snippet = item.get("content") or ""
    if engine:
        snippet = f"[{engine}] {snippet}" if snippet else f"[{engine}]"
    return Evidence(
        title=item.get("title") or item.get("url", ""),
        url=item.get("url", ""),
        snippet=snippet or None,
        score=0.6,
        source_channel="searxng",
        fetched_at=fetched_at,
    )
