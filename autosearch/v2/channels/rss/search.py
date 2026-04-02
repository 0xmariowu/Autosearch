from __future__ import annotations

from autosearch.v2.channels._engines.ddgs import search_ddgs_web


async def search(query: str, max_results: int = 10) -> list[dict]:
    return await search_ddgs_web(f"{query} RSS feed", max_results)
