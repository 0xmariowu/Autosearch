from __future__ import annotations

import sys
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

BASE_URL = "https://www.reddit.com/"
SEARCH_URL = urljoin(BASE_URL, "search.json")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


async def _search_json_api(query: str, max_results: int) -> list[dict]:
    """Try Reddit's JSON API (may 403 without auth)."""
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = await client.get(
            SEARCH_URL,
            params={"q": query, "limit": min(25, max_results)},
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, dict):
            return []

        results: list[dict] = []
        for post in data.get("children", []):
            post_data = post.get("data", {})
            permalink = post_data.get("permalink", "")
            title = post_data.get("title", "")
            if not permalink or not title:
                continue

            result_url = urljoin(BASE_URL, permalink)
            content = (post_data.get("selftext", "") or "")[:500]
            extra_metadata: dict = {
                "subreddit": post_data.get("subreddit", ""),
                "score": post_data.get("score", 0),
                "num_comments": post_data.get("num_comments", 0),
            }
            created_utc = post_data.get("created_utc")
            if isinstance(created_utc, (int, float)):
                extra_metadata["published_at"] = datetime.fromtimestamp(
                    created_utc, tz=timezone.utc
                ).isoformat()

            results.append(
                make_result(
                    url=result_url,
                    title=title,
                    snippet=content,
                    source="reddit",
                    query=query,
                    extra_metadata=extra_metadata,
                )
            )
            if len(results) >= max_results:
                break

        return results


async def _search_ddgs_fallback(query: str, max_results: int) -> list[dict]:
    """Fallback: search Reddit via DuckDuckGo site: filter."""
    from channels._engines.ddgs import search_ddgs_site

    return await search_ddgs_site(query, "reddit.com", max_results)


async def search(query: str, max_results: int = 10) -> list[dict]:
    # Try JSON API first, fall back to ddgs
    try:
        results = await _search_json_api(query, max_results)
        if results:
            return results
    except Exception as exc:
        print(f"[reddit] JSON API failed, trying fallback: {exc}", file=sys.stderr)

    try:
        return await _search_ddgs_fallback(query, max_results)
    except Exception as exc:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="reddit", error_type="network", message=f"all methods failed: {exc}"
        ) from exc
