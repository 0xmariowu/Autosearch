"""Juejin native search API.

Uses api.juejin.cn/search_api/v1/search with aid=2608.
Verified: 25/25 tests passed. No auth needed.
Full article content API is broken (returns 参数错误), only briefs available.
Falls back to Baidu Kaifa on API failure.
"""

from __future__ import annotations

import sys

import httpx

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
_SEARCH_URL = "https://api.juejin.cn/search_api/v1/search"
_BASE_PARAMS = {
    "aid": "2608",
    "uuid": "7259393293459605051",
    "spider": "0",
    "id_type": "0",
    "sort_type": "0",
    "version": "1",
}


async def search(query: str, max_results: int = 10) -> list[dict]:
    try:
        results = await _search_native(query, max_results)
        if results:
            return results
    except Exception as exc:
        print(
            f"[juejin] native API failed, falling back to Baidu: {exc}", file=sys.stderr
        )

    from channels._engines.baidu import search_baidu

    return await search_baidu(query, site="juejin.cn", max_results=max_results)


async def _search_native(query: str, max_results: int) -> list[dict]:
    from lib.search_runner import DEFAULT_TIMEOUT, make_result

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        params = {
            **_BASE_PARAMS,
            "query": query,
            "cursor": "0",
            "limit": str(min(max_results, 20)),
            "search_type": "0",
        }
        resp = await client.get(
            _SEARCH_URL,
            params=params,
            headers={"User-Agent": _UA},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("err_no") != 0:
            return []

        items = data.get("data") or []
        if not items:
            return []

        results: list[dict] = []
        for item in items:
            rm = item.get("result_model", {})
            ai = rm.get("article_info", {})
            author_info = rm.get("author_user_info", {})

            article_id = ai.get("article_id", "")
            title = str(ai.get("title", "") or "").strip()
            if not article_id or not title:
                continue

            url = f"https://juejin.cn/post/{article_id}"
            brief = str(ai.get("brief_content", "") or "").strip()

            metadata: dict = {}
            author = author_info.get("user_name", "")
            if author:
                metadata["author"] = str(author)

            tags = rm.get("tags", [])
            if tags:
                metadata["tags"] = [
                    t.get("tag_name", "") for t in tags if t.get("tag_name")
                ]

            results.append(
                make_result(
                    url=url,
                    title=title,
                    snippet=brief or title,
                    source="juejin",
                    query=query,
                    extra_metadata=metadata,
                )
            )
            if len(results) >= max_results:
                break

        return results
