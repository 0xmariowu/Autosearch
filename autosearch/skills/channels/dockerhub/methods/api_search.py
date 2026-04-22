"""Docker Hub public registry search — free, no auth required."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="dockerhub")

_SEARCH_URL = "https://hub.docker.com/v2/search/repositories/"
_MAX_RESULTS = 10
_HTTP_TIMEOUT = 15.0


async def search(query: SubQuery) -> list[Evidence]:
    try:
        return await _search_images(query.text)
    except Exception as exc:
        LOGGER.warning("dockerhub_search_failed", reason=str(exc))
        return []


async def _search_images(query: str) -> list[Evidence]:
    params = {"query": query, "page_size": _MAX_RESULTS, "page": 1}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(_SEARCH_URL, params=params)
        resp.raise_for_status()
    data = resp.json()
    results = data.get("results") or []
    fetched_at = datetime.now(UTC)
    return [_to_evidence(item, fetched_at) for item in results if item.get("repo_name")]


def _to_evidence(item: dict, fetched_at: datetime) -> Evidence:
    repo_name = item.get("repo_name") or ""
    description = item.get("short_description") or ""
    pull_count = item.get("pull_count") or 0
    star_count = item.get("star_count") or 0
    is_official = item.get("is_official") or False

    url = f"https://hub.docker.com/r/{repo_name}"
    title = f"{'[Official] ' if is_official else ''}{repo_name}"
    snippet = f"{description} | pulls: {pull_count:,} | stars: {star_count}"

    return Evidence(
        title=title,
        url=url,
        snippet=snippet,
        score=0.6,
        source_channel="dockerhub",
        fetched_at=fetched_at,
    )
