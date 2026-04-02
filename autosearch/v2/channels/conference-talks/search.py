from __future__ import annotations

from autosearch.v2.channels.youtube.search import search as youtube_search


async def search(query: str, max_results: int = 10) -> list[dict]:
    return await youtube_search(f"conference talk keynote {query}", max_results)
