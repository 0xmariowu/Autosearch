"""百度贴吧搜索渠道 — 免费，无需 API key。"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="tieba")

_SEARCH_URL = "https://tieba.baidu.com/f/search/res"
_HTTP_TIMEOUT = 15.0
_MAX_RESULTS = 10

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://tieba.baidu.com/",
}


async def search(query: SubQuery) -> list[Evidence]:
    try:
        return await _search_tieba(query.text)
    except Exception as exc:
        LOGGER.warning("tieba_search_failed", reason=str(exc))
        return []


async def _search_tieba(query: str) -> list[Evidence]:
    params = {
        "qw": query,
        "rn": str(_MAX_RESULTS),
        "pn": "0",
        "sm": "1",
    }
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await client.get(_SEARCH_URL, params=params)
        resp.raise_for_status()

    return _parse_results(resp.text)


def _parse_results(html: str) -> list[Evidence]:
    """Extract post titles, URLs, and snippets from Tieba search result HTML."""
    results: list[Evidence] = []
    fetched_at = datetime.now(UTC)

    # Extract post links and titles from search results
    # Pattern: <a href="/p/XXXXXXX" title="...">...</a> or similar
    post_pattern = re.compile(
        r'<a[^>]+href="(/p/\d+)"[^>]*>([^<]{3,100})</a>',
        re.IGNORECASE,
    )
    # Extract snippets from search result items
    snippet_pattern = re.compile(
        r'class="[^"]*content[^"]*"[^>]*>(.*?)</[^>]+>',
        re.IGNORECASE | re.DOTALL,
    )

    seen_urls: set[str] = set()
    posts = post_pattern.findall(html)

    for path, title in posts:
        title = re.sub(r"<[^>]+>", "", title).strip()
        if not title or len(title) < 3:
            continue
        url = f"https://tieba.baidu.com{path}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        results.append(
            Evidence(
                title=title,
                url=url,
                snippet=None,
                score=0.6,
                source_channel="tieba",
                fetched_at=fetched_at,
            )
        )
        if len(results) >= _MAX_RESULTS:
            break

    return results
