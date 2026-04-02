from __future__ import annotations

import sys

from autosearch.v2.search_runner import make_result


async def search_ddgs_web(
    query: str, max_results: int = 10, source: str = "web-ddgs"
) -> list[dict]:
    try:
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
    except Exception as exc:
        print(f"[search_runner] ddgs web error: {exc}", file=sys.stderr)
        return []


async def search_ddgs_site(query: str, site: str, max_results: int = 10) -> list[dict]:
    return await search_ddgs_web(
        f"site:{site} {query}",
        max_results=max_results,
        source=site.split(".")[0],
    )
