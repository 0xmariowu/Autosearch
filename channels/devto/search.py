from __future__ import annotations

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result


async def search(query: str, max_results: int = 10) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(
                "https://dev.to/api/articles",
                params={"per_page": max_results, "tag": "", "query": query},
            )
            response.raise_for_status()
            articles = response.json()
    except Exception as exc:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="devto", error_type="network", message=str(exc)
        ) from exc

    results: list[dict] = []
    for article in articles[:max_results]:
        metadata = {}
        if article.get("published_at"):
            metadata["published_at"] = article["published_at"]
        if article.get("public_reactions_count") is not None:
            metadata["public_reactions_count"] = article["public_reactions_count"]
        if article.get("comments_count") is not None:
            metadata["comments_count"] = article["comments_count"]

        tag_list = article.get("tag_list")
        if isinstance(tag_list, list) and tag_list:
            metadata["tags"] = tag_list

        user = article.get("user")
        if isinstance(user, dict):
            author = user.get("name") or user.get("username")
            if author:
                metadata["author"] = author
            if user.get("username"):
                metadata["username"] = user["username"]

        results.append(
            make_result(
                url=article.get("url", ""),
                title=article.get("title", ""),
                snippet=article.get("description", "") or "",
                source="devto",
                query=query,
                extra_metadata=metadata,
            )
        )

    return results
