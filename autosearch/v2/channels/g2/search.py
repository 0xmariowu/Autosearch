from __future__ import annotations

from autosearch.v2.channels._engines.ddgs import search_ddgs_site


async def search(query: str, max_results: int = 10) -> list[dict]:
    return await search_ddgs_site(query, "g2.com", max_results)
