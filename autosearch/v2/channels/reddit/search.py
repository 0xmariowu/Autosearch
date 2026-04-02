from __future__ import annotations

import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx

from autosearch.v2.search_runner import DEFAULT_TIMEOUT, make_result

BASE_URL = "https://www.reddit.com/"
SEARCH_URL = urljoin(BASE_URL, "search.json")
PAGE_SIZE = 25
USER_AGENT = (
    "autosearch/2.0 (+https://github.com; direct channel port from SearXNG reddit)"
)


def _valid_thumbnail(url: str) -> bool:
    parsed = urlparse(url or "")
    return bool(parsed.netloc and parsed.path)


async def search(query: str, max_results: int = 10) -> list[dict]:
    image_results: list[dict] = []
    text_results: list[dict] = []
    after: str | None = None

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            while len(image_results) + len(text_results) < max_results:
                response = await client.get(
                    SEARCH_URL,
                    params={
                        "q": query,
                        "limit": min(PAGE_SIZE, max_results),
                        **({"after": after} if after else {}),
                    },
                )
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data")
                if not isinstance(data, dict):
                    return []

                posts = data.get("children", [])
                if not posts:
                    break

                for post in posts:
                    post_data = post.get("data", {})
                    permalink = post_data.get("permalink", "")
                    title = post_data.get("title", "")
                    if not permalink or not title:
                        continue

                    result_url = urljoin(BASE_URL, permalink)
                    thumbnail = post_data.get("thumbnail", "") or ""
                    extra_metadata = {
                        "author": post_data.get("author", ""),
                        "subreddit": post_data.get("subreddit", ""),
                        "score": post_data.get("score", 0),
                        "num_comments": post_data.get("num_comments", 0),
                    }

                    if _valid_thumbnail(thumbnail):
                        image_results.append(
                            make_result(
                                url=result_url,
                                title=title,
                                snippet=(post_data.get("selftext", "") or "")[:500],
                                source="reddit",
                                query=query,
                                extra_metadata={
                                    **extra_metadata,
                                    "kind": "image",
                                    "image_url": post_data.get("url", ""),
                                    "thumbnail": thumbnail,
                                },
                            )
                        )
                    else:
                        content = (post_data.get("selftext", "") or "")[:500]
                        created_utc = post_data.get("created_utc")
                        if isinstance(created_utc, (int, float)):
                            extra_metadata["published_at"] = datetime.fromtimestamp(
                                created_utc, tz=timezone.utc
                            ).isoformat()
                        extra_metadata["kind"] = "text"
                        text_results.append(
                            make_result(
                                url=result_url,
                                title=title,
                                snippet=content,
                                source="reddit",
                                query=query,
                                extra_metadata=extra_metadata,
                            )
                        )

                    if len(image_results) + len(text_results) >= max_results:
                        break

                after = data.get("after")
                if not after:
                    break

        return (image_results + text_results)[:max_results]
    except Exception as exc:
        print(f"[reddit] search failed: {exc}", file=sys.stderr)
        return []
