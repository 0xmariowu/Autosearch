from __future__ import annotations

from channels._engines.baidu import search_baidu


async def search(query: str, max_results: int = 10) -> list[dict]:
    return await search_baidu(query, site="xiaoyuzhoufm.com", max_results=max_results)
