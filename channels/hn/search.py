from __future__ import annotations

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Search Hacker News via Algolia API."""
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": query, "hitsPerPage": max_results, "tags": "story"},
            )
            if resp.status_code != 200:
                return []
            hits = resp.json().get("hits", [])
            results = []
            for h in hits:
                metadata = {}
                if h.get("created_at"):
                    metadata["created_utc"] = h["created_at"]
                if h.get("points"):
                    metadata["points"] = h["points"]
                url = (
                    h.get("url")
                    or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"
                )
                results.append(
                    make_result(
                        url=url,
                        title=h.get("title", ""),
                        snippet=f"Points: {h.get('points', 0)} | Comments: {h.get('num_comments', 0)}",
                        source="hn",
                        query=query,
                        extra_metadata=metadata,
                    )
                )
            return results
    except Exception as e:
        from lib.search_runner import SearchError

        raise SearchError(channel="hn", error_type="network", message=str(e)) from e
