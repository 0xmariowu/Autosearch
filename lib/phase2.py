from __future__ import annotations

import asyncio
import sys

from lib.search_runner import dedup_results


async def _search_subreddit(
    subreddit: str, original_query: str, max_per_entity: int
) -> list[dict]:
    from channels.reddit.search import search_subreddit

    return await search_subreddit(subreddit, original_query, max_per_entity)


async def _search_x_handle(
    handle: str, original_query: str, max_per_entity: int
) -> list[dict]:
    from channels.twitter.search import search as twitter_search

    query = f"from:{handle} {original_query}"
    return await twitter_search(query, max_per_entity)


async def run_phase2(
    entities: dict[str, list[str]], original_query: str, max_per_entity: int = 5
) -> list[dict]:
    try:
        tasks = [
            _search_subreddit(subreddit, original_query, max_per_entity)
            for subreddit in (entities.get("subreddits") or [])
        ]
        tasks.extend(
            _search_x_handle(handle, original_query, max_per_entity)
            for handle in (entities.get("x_handles") or [])
        )

        if not tasks:
            return []

        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[dict] = []
        for item in gathered:
            if isinstance(item, Exception):
                continue
            results.extend(item)

        return dedup_results(results)
    except Exception as exc:
        print(f"[phase2] {exc}", file=sys.stderr)
        return []
