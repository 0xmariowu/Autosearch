"""LinkedIn public content via Jina Reader.

1:1 adapted from Agent-Reach agent_reach/channels/linkedin.py pattern.
Free, no auth needed for public LinkedIn pages.
"""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime

import httpx

from autosearch.core.models import Evidence, SubQuery

_JINA_BASE = "https://r.jina.ai"
_TIMEOUT = 15
_HEADERS = {
    "Accept": "application/json",
    "X-Return-Format": "markdown",
}


async def search(query: SubQuery) -> list[Evidence]:
    """Fetch LinkedIn company/profile page via Jina Reader."""
    fetched_at = datetime.now(UTC)

    # Build a LinkedIn search URL — Jina can fetch public LinkedIn pages
    encoded = urllib.parse.quote(query.text)
    target_url = f"https://www.linkedin.com/search/results/all/?keywords={encoded}"
    jina_url = f"{_JINA_BASE}/{target_url}"

    # Bug 2 (fix-plan v8 follow-up): typed errors instead of silent [] so
    # 401 / 403 / 429 / network failures don't masquerade as "no LinkedIn
    # results found".
    from autosearch.channels.base import (
        ChannelAuthError,
        PermanentError,
        RateLimited,
        TransientError,
    )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(jina_url, headers=_HEADERS)
    except httpx.HTTPError as exc:
        raise TransientError(f"linkedin via Jina network error: {exc}") from exc

    if resp.status_code in (401, 403):
        raise ChannelAuthError(f"linkedin via Jina rejected (HTTP {resp.status_code})")
    if resp.status_code == 429:
        raise RateLimited("linkedin via Jina rate limit (HTTP 429)")
    if resp.status_code != 200:
        raise PermanentError(f"linkedin via Jina HTTP {resp.status_code}")

    content = resp.text[:2000].strip()
    if not content:
        # Legitimate "Jina returned 200 with empty body" — keep as [].
        return []

    return [
        Evidence(
            url=target_url,
            title=f"LinkedIn: {query.text}",
            snippet=content[:300],
            content=content,
            source_channel="linkedin:jina",
            fetched_at=fetched_at,
        )
    ]
