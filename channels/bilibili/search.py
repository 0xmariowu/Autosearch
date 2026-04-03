from __future__ import annotations

import html
import random
import re
import string
import sys
from datetime import datetime, timezone

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

BASE_URL = "https://api.bilibili.com/x/web-interface/search/type"
RESULTS_PER_PAGE = 20
REFERER = "https://www.bilibili.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
COOKIE = {
    "innersign": "0",
    "buvid3": "".join(random.choice(string.hexdigits) for _ in range(16)) + "infoc",
    "i-wanna-go-back": "-1",
    "b_ut": "7",
    "FEED_LIVE_VERSION": "V8",
    "header_theme_version": "undefined",
    "home_feed_column": "4",
}


def _html_to_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(text).strip()


def _parse_duration(duration: str) -> tuple[str, int | None]:
    raw = (duration or "").strip()
    if not raw:
        return "", None

    parts = raw.split(":")
    if not all(part.isdigit() for part in parts):
        return raw, None

    total = 0
    for part in parts:
        total = total * 60 + int(part)

    # SearXNG discards durations that appear to exceed one hour.
    if total > 60 * 60:
        return "", None
    return raw, total


async def search(query: str, max_results: int = 10) -> list[dict]:
    results: list[dict] = []
    total_pages = max(1, (max_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"Referer": REFERER, "User-Agent": USER_AGENT},
            cookies=COOKIE,
        ) as client:
            for page in range(1, total_pages + 1):
                response = await client.get(
                    BASE_URL,
                    params={
                        "__refresh__": "true",
                        "page": page,
                        "page_size": RESULTS_PER_PAGE,
                        "single_column": "0",
                        "keyword": query,
                        "search_type": "video",
                    },
                )
                response.raise_for_status()
                payload = response.json()

                items = payload.get("data", {}).get("result", [])
                if not items:
                    break

                for item in items:
                    title = _html_to_text(item.get("title", ""))
                    url = item.get("arcurl", "")
                    if not title or not url:
                        continue

                    description = item.get("description", "") or ""
                    thumbnail = item.get("pic", "") or ""
                    if thumbnail.startswith("//"):
                        thumbnail = f"https:{thumbnail}"

                    published_at = None
                    pubdate = item.get("pubdate")
                    if isinstance(pubdate, (int, float)):
                        published_at = datetime.fromtimestamp(
                            pubdate, tz=timezone.utc
                        ).isoformat()

                    duration_raw, duration_seconds = _parse_duration(
                        item.get("duration", "")
                    )
                    video_id = item.get("aid")
                    metadata = {
                        "author": item.get("author", ""),
                        "thumbnail": thumbnail,
                        "video_id": video_id,
                        "iframe_src": (
                            f"https://player.bilibili.com/player.html?aid={video_id}"
                            "&high_quality=1&autoplay=false&danmaku=0"
                        )
                        if video_id
                        else "",
                    }
                    if published_at:
                        metadata["published_at"] = published_at
                    if duration_raw:
                        metadata["duration"] = duration_raw
                    if duration_seconds is not None:
                        metadata["duration_seconds"] = duration_seconds

                    results.append(
                        make_result(
                            url=url,
                            title=title,
                            snippet=description,
                            source="bilibili",
                            query=query,
                            extra_metadata=metadata,
                        )
                    )
                    if len(results) >= max_results:
                        return results[:max_results]

        return results[:max_results]
    except Exception as exc:
        print(f"[bilibili] search failed: {exc}", file=sys.stderr)
        return []
