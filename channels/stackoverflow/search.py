from __future__ import annotations

import html
import sys

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

API_SITE = "stackoverflow"
API_SORT = "activity"
API_ORDER = "desc"
PAGE_SIZE = 10
SEARCH_API = "https://api.stackexchange.com/2.3/search/advanced"


async def search(query: str, max_results: int = 10) -> list[dict]:
    results: list[dict] = []
    total_pages = max(1, (max_results + PAGE_SIZE - 1) // PAGE_SIZE)

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            for page in range(1, total_pages + 1):
                response = await client.get(
                    SEARCH_API,
                    params={
                        "q": query,
                        "page": page,
                        "pagesize": PAGE_SIZE,
                        "site": API_SITE,
                        "sort": API_SORT,
                        "order": API_ORDER,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                items = payload.get("items", [])
                if not items:
                    break

                for item in items:
                    question_id = item.get("question_id")
                    title = html.unescape(item.get("title", "") or "")
                    if not question_id or not title:
                        continue

                    tags = item.get("tags", [])
                    owner = item.get("owner", {}).get("display_name", "")
                    parts = [f"[{', '.join(tags)}]" if tags else ""]
                    if owner:
                        parts.append(owner)
                    if item.get("is_answered"):
                        parts.append("is answered")
                    parts.append(f"score: {item.get('score', 0)}")
                    snippet = " // ".join(part for part in parts if part)

                    metadata = {
                        "question_id": question_id,
                        "tags": tags,
                        "owner": owner,
                        "is_answered": bool(item.get("is_answered")),
                        "score": item.get("score", 0),
                        "answer_count": item.get("answer_count", 0),
                    }

                    results.append(
                        make_result(
                            url=f"https://{API_SITE}.com/q/{question_id}",
                            title=title,
                            snippet=html.unescape(snippet),
                            source="stackoverflow",
                            query=query,
                            extra_metadata=metadata,
                        )
                    )
                    if len(results) >= max_results:
                        return results[:max_results]

        return results[:max_results]
    except Exception as exc:
        print(f"[stackoverflow] search failed: {exc}", file=sys.stderr)
        return []
