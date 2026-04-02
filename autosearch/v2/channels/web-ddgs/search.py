from __future__ import annotations

import sys

from autosearch.v2.search_runner import make_result


async def search(query: str, max_results: int = 10) -> list[dict]:
    """General web search via DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    make_result(
                        url=r.get("href", ""),
                        title=r.get("title", ""),
                        snippet=r.get("body", ""),
                        source="web-ddgs",
                        query=query,
                    )
                )
        return results
    except Exception as e:
        print(f"[search_runner] ddgs web error: {e}", file=sys.stderr)
        return []
