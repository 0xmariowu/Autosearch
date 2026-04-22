"""Firecrawl URL-to-Markdown scraper — requires FIRECRAWL_API_KEY."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import MethodUnavailable
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="tool", channel="fetch-firecrawl")

_API_URL = "https://api.firecrawl.dev/v1/scrape"
_HTTP_TIMEOUT = 30.0


async def search(query: SubQuery) -> list[Evidence]:
    """Accept a URL as the query text and return one Evidence with the page markdown."""
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise MethodUnavailable("FIRECRAWL_API_KEY is not set")

    url = query.text.strip()
    if not url.startswith(("http://", "https://")):
        LOGGER.warning("firecrawl_invalid_url", url=url)
        return []

    try:
        return await _scrape(url, api_key)
    except MethodUnavailable:
        raise
    except Exception as exc:
        LOGGER.warning("firecrawl_scrape_failed", url=url, reason=str(exc))
        return []


async def _scrape(url: str, api_key: str) -> list[Evidence]:
    payload = {"url": url, "formats": ["markdown"]}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
    data = resp.json()
    markdown = (data.get("data") or {}).get("markdown") or ""
    title = (data.get("data") or {}).get("metadata", {}).get("title") or url

    if not markdown:
        return []

    return [
        Evidence(
            title=title,
            url=url,
            content=markdown[:4000],
            score=0.9,
            source_channel="fetch-firecrawl",
            fetched_at=datetime.now(UTC),
        )
    ]
