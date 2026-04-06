"""Douyin search: hot search → Baidu fallback.

Keyword search requires msToken (browser JS signature, not replicable).
Hot search endpoint works without any auth: 51 trending items with metadata.
Query filters hot items by relevance.
"""

from __future__ import annotations

import sys

import httpx

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
_HOT_URL = "https://www.douyin.com/aweme/v1/web/hot/search/list/"


async def search(query: str, max_results: int = 10) -> list[dict]:
    try:
        results = await _search_hot(query, max_results)
        if results:
            return results
    except Exception as exc:
        print(f"[douyin] hot search failed: {exc}", file=sys.stderr)

    from channels._engines.baidu import search_baidu

    return await search_baidu(query, site="douyin.com", max_results=max_results)


async def _search_hot(query: str, max_results: int) -> list[dict]:
    from lib.search_runner import DEFAULT_TIMEOUT, make_result

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT, follow_redirects=True
    ) as client:
        resp = await client.get(
            _HOT_URL,
            params={
                "device_platform": "webapp",
                "aid": "6383",
                "version_name": "23.5.0",
            },
            headers={"User-Agent": _UA, "Referer": "https://www.douyin.com/"},
        )
        if resp.is_error:
            return []

        data = resp.json()
        items = data.get("data", {}).get("word_list", [])
        if not items:
            return []

        query_tokens = set(query.lower().split())
        results: list[dict] = []

        for item in items:
            word = str(item.get("word", "") or "").strip()
            if not word:
                continue

            word_lower = word.lower()
            relevant = (
                not query.strip()
                or any(t in word_lower for t in query_tokens)
                or any(t in query.lower() for t in word_lower.split())
            )
            if not relevant:
                continue

            hot_value = item.get("hot_value", 0)
            url = f"https://www.douyin.com/search/{word}"

            metadata: dict = {"hot_value": hot_value}
            sentence_id = item.get("sentence_id", "")
            if sentence_id:
                metadata["sentence_id"] = sentence_id

            results.append(
                make_result(
                    url=url,
                    title=word,
                    snippet=f"抖音热搜: {word} (热度 {hot_value:,})"
                    if hot_value
                    else f"抖音热搜: {word}",
                    source="douyin",
                    query=query,
                    extra_metadata=metadata,
                )
            )
            if len(results) >= max_results:
                break

        # If no relevant items, return top hot items
        if not results and items and query.strip():
            for item in items[:max_results]:
                word = str(item.get("word", "") or "").strip()
                if not word:
                    continue
                results.append(
                    make_result(
                        url=f"https://www.douyin.com/search/{word}",
                        title=word,
                        snippet=f"抖音热搜: {word}",
                        source="douyin",
                        query=query,
                        extra_metadata={"hot_value": item.get("hot_value", 0)},
                    )
                )

        return results
