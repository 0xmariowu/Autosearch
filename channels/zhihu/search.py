"""Zhihu search: auto-cookie → Baidu Kaifa fallback.

With z_c0 cookie: /api/v4/search_v3 (search + content).
Without: Baidu Kaifa site:zhihu.com (URL-filtered).
Cookie: ZHIHU_COOKIE env var → browser-cookie3.
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

    cookies = get_cookies(".zhihu.com", "ZHIHU_COOKIE")
    if has_cookies(cookies, ["z_c0"]):
        try:
            results = await _search_native(query, cookies, max_results)
            if results:
                return results
        except Exception as exc:
            print(f"[zhihu] native failed: {exc}", file=sys.stderr)

    from channels._engines.baidu import search_baidu

    return await search_baidu(query, site="zhihu.com", max_results=max_results)


async def _search_native(
    query: str, cookies: dict[str, str], max_results: int
) -> list[dict]:
    from channels._engines.cookie_auth import cookie_header
    from lib.search_runner import DEFAULT_TIMEOUT, make_result

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            "https://www.zhihu.com/api/v4/search_v3",
            params={
                "t": "general",
                "q": query,
                "limit": min(max_results, 10),
                "offset": 0,
            },
            headers={
                "User-Agent": _UA,
                "Cookie": cookie_header(cookies),
                "Referer": "https://www.zhihu.com/search",
            },
        )
        if resp.status_code in (401, 403):
            return []
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            return []

        items = data.get("data", [])
        results: list[dict] = []
        for item in items:
            obj = item.get("object", item)
            item_type = item.get("type", obj.get("type", ""))
            title = re.sub(
                r"<[^>]+>", "", str(obj.get("title", obj.get("name", "")) or "")
            ).strip()
            if not title:
                continue

            url = obj.get("url", "")
            if not url or "zhihu.com" not in url:
                obj_id = obj.get("id", "")
                if item_type == "article" and obj_id:
                    url = f"https://zhuanlan.zhihu.com/p/{obj_id}"
                elif item_type == "answer" and obj_id:
                    url = f"https://www.zhihu.com/answer/{obj_id}"
                elif not url:
                    continue

            excerpt = re.sub(
                r"<[^>]+>",
                "",
                str(obj.get("excerpt", obj.get("description", "")) or ""),
            ).strip()
            metadata: dict = {}
            author = obj.get("author", {})
            if isinstance(author, dict) and author.get("name"):
                metadata["author"] = author["name"]
            for field, key in [
                ("voteup_count", "voteup_count"),
                ("comment_count", "comment_count"),
            ]:
                val = obj.get(field)
                if val is not None:
                    metadata[key] = val

            content = obj.get("content", "")
            if content:
                text = re.sub(r"<[^>]+>", " ", str(content))
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 100:
                    metadata["extracted_content"] = text[:3000]

            results.append(
                make_result(
                    url=url,
                    title=title,
                    snippet=excerpt or title,
                    source="zhihu",
                    query=query,
                    extra_metadata=metadata,
                )
            )
            if len(results) >= max_results:
                break
        return results
