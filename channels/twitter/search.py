from __future__ import annotations

from channels._engines.ddgs import search_ddgs_web


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Search Twitter/X via DuckDuckGo, querying both domains."""
    try:
        # Search both twitter.com and x.com for maximum coverage
        half = max(3, (max_results + 1) // 2)

        twitter_results = await search_ddgs_web(
            f"site:twitter.com {query}", half, source="twitter"
        )
        x_results = await search_ddgs_web(f"site:x.com {query}", half, source="twitter")

        # Merge and dedup by URL stem (twitter.com/user/status/ID == x.com/user/status/ID)
        seen: set[str] = set()
        merged: list[dict] = []

        for r in twitter_results + x_results:
            # Extract status ID for dedup
            url = r.get("url", "")
            # Normalize: extract /status/XXXXX part
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

    except Exception as exc:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="twitter", error_type="network", message=str(exc)
        ) from exc
