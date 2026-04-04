from __future__ import annotations

import asyncio
import sys

from lib.search_runner import make_result


def _sync_ddgs_search(query: str, max_results: int, source: str) -> list[dict]:
    """Run DDGS search synchronously — called via run_in_executor."""
    from ddgs import DDGS

    results = []
    with DDGS() as ddgs:
        for result in ddgs.text(query, max_results=max_results):
            results.append(
                make_result(
                    url=result.get("href", ""),
                    title=result.get("title", ""),
                    snippet=result.get("body", ""),
                    source=source,
                    query=query,
                )
            )
    return results


async def search_ddgs_web(
    query: str, max_results: int = 10, source: str = "web-ddgs"
) -> list[dict]:
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _sync_ddgs_search, query, max_results, source
        )
    except Exception as exc:
        print(f"[search_runner] ddgs web error: {exc}", file=sys.stderr)
        return []


async def search_ddgs_site(query: str, site: str, max_results: int = 10) -> list[dict]:
    return await search_ddgs_web(
        f"site:{site} {query}",
        max_results=max_results,
        source=site.split(".")[0],
    )
