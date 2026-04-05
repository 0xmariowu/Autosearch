"""Xueqiu search: auto-cookie → Baidu Kaifa fallback.

With xq_a_token cookie: xueqiu.com/query/v1/search/status.json.
Without: Baidu Kaifa site:xueqiu.com (URL-filtered).
Cookie: XUEQIU_COOKIE env var → browser-cookie3.
"""

from __future__ import annotations

import re
import sys

import httpx

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


async def search(query: str, max_results: int = 10) -> list[dict]:
    from channels._engines.cookie_auth import get_cookies, has_cookies

    cookies = get_cookies(".xueqiu.com", "XUEQIU_COOKIE")
    if has_cookies(cookies, ["xq_a_token"]):
        try:
            results = await _search_native(query, cookies, max_results)
            if results:
                return results
        except Exception as exc:
            print(f"[xueqiu] native failed: {exc}", file=sys.stderr)

    from channels._engines.baidu import search_baidu

    return await search_baidu(query, site="xueqiu.com", max_results=max_results)


async def _search_native(
    query: str, cookies: dict[str, str], max_results: int
) -> list[dict]:
    from channels._engines.cookie_auth import cookie_header
    from lib.search_runner import DEFAULT_TIMEOUT, make_result

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            "https://xueqiu.com/query/v1/search/status.json",
            params={
                "q": query,
                "count": min(max_results, 20),
                "sort": "time",
                "source": "all",
                "page": 1,
            },
            headers={
                "User-Agent": _UA,
                "Cookie": cookie_header(cookies),
                "Referer": "https://xueqiu.com/",
            },
        )
        if resp.status_code in (401, 403):
            return []
        resp.raise_for_status()
        data = resp.json()
        if data.get("error_code"):
            return []

        items = data.get("list", [])
        results: list[dict] = []
        for item in items:
            title = re.sub(
                r"<[^>]+>",
                "",
                str(item.get("title", item.get("description", "")) or ""),
            ).strip()
            if not title:
                continue

            user_id = item.get("user_id", item.get("uid", ""))
            status_id = item.get("id", "")
            url = (
                f"https://xueqiu.com/{user_id}/{status_id}"
                if user_id and status_id
                else ""
            )
            if not url:
                target = item.get("target", "")
                url = f"https://xueqiu.com{target}" if target else ""
            if not url:
                continue

            text = re.sub(
                r"<[^>]+>",
                " ",
                str(item.get("text", item.get("description", "")) or ""),
            )
            text = re.sub(r"\s+", " ", text).strip()

            metadata: dict = {}
            if text and len(text) > 50:
                metadata["extracted_content"] = text[:3000]
            screen_name = item.get(
                "screen_name", item.get("user", {}).get("screen_name", "")
            )
            if screen_name:
                metadata["author"] = str(screen_name)
            for field, key in [
                ("reply_count", "num_comments"),
                ("retweet_count", "reposts"),
                ("like_count", "likes"),
            ]:
                val = item.get(field)
                if val is not None:
                    metadata[key] = val

            created_at = item.get("created_at")
            if created_at:
                try:
                    from datetime import datetime, timezone

                    dt = datetime.fromtimestamp(int(created_at) / 1000, tz=timezone.utc)
                    metadata["published_at"] = dt.isoformat()
                except (ValueError, TypeError, OSError):
                    pass

            results.append(
                make_result(
                    url=url,
                    title=title[:100],
                    snippet=(text[:300] if text else title),
                    source="xueqiu",
                    query=query,
                    extra_metadata=metadata,
                )
            )
            if len(results) >= max_results:
                break
        return results
