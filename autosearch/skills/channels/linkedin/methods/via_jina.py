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

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(jina_url, headers=_HEADERS)
            if resp.status_code != 200:
                return []
            content = resp.text[:2000].strip()
    except Exception:
        return []

    if not content:
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
