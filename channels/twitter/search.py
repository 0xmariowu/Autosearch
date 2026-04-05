from __future__ import annotations

import sys

from channels._engines.ddgs import search_ddgs_web
from lib.search_runner import make_result


async def _search_graphql(query: str, max_results: int) -> list[dict]:
    """Try GraphQL SearchTimeline (requires browser cookies or env vars)."""
    try:
        from channels.twitter.graphql import search_graphql

        tweets = await search_graphql(query, max_results)
        if not tweets:
            return []

        results: list[dict] = []
        for tweet in tweets:
            results.append(
                make_result(
                    url=tweet.get("url", ""),
                    title=tweet.get("text", "")[:200],
                    snippet=tweet.get("text", "")[:500],
                    source="twitter",
                    query=query,
                    extra_metadata={
                        "likes": tweet.get("likes", 0),
                        "reposts": tweet.get("reposts", 0),
                        "replies": tweet.get("replies", 0),
                        "author_handle": tweet.get("author_handle", ""),
                        "published_at": tweet.get("created_at", ""),
                    },
                )
            )
            if len(results) >= max_results:
                break
        return results
    except Exception as exc:
        print(f"[twitter] GraphQL failed: {exc}", file=sys.stderr)
        return []


async def _search_ddgs(query: str, max_results: int) -> list[dict]:
    """Search Twitter/X via DuckDuckGo site-search (no auth needed)."""
    half = max(3, (max_results + 1) // 2)

    twitter_results = await search_ddgs_web(
        f"site:twitter.com {query}", half, source="twitter"
    )
    x_results = await search_ddgs_web(f"site:x.com {query}", half, source="twitter")

    # Merge and dedup by URL stem (twitter.com/user/status/ID == x.com/user/status/ID)
    seen: set[str] = set()
    merged: list[dict] = []

    for r in twitter_results + x_results:
        url = r.get("url", "")
        key = url
        if "/status/" in url:
            key = url.split("/status/")[-1].split("?")[0]

        if key in seen:
            continue
        seen.add(key)
        merged.append(r)

        if len(merged) >= max_results:
            break

    return merged[:max_results]


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Search Twitter/X — GraphQL first, DDGS fallback."""
    try:
        # Try GraphQL (cookie-based, rich engagement data)
        results = await _search_graphql(query, max_results)
        if results:
            return results

        # Fall back to DDGS site-search
        return await _search_ddgs(query, max_results)
    except Exception as exc:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="twitter", error_type="network", message=str(exc)
        ) from exc
