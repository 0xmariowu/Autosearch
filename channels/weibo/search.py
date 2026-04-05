"""Weibo search: auto-cookie → Baidu Kaifa fallback.

With SUB cookie: m.weibo.cn/api/container/getIndex (search + full posts).
Without: Baidu Kaifa site:weibo.com (URL-filtered).
Cookie: WEIBO_COOKIE env var → browser-cookie3.

Note: visitor passport cookies are NOT sufficient (ok:-100).
Only real login cookies work for search.
"""

from __future__ import annotations

import re
import sys

import httpx

_UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


async def search(query: str, max_results: int = 10) -> list[dict]:
    from channels._engines.cookie_auth import get_cookies, has_cookies

    cookies = get_cookies(".weibo.com", "WEIBO_COOKIE")
    if not has_cookies(cookies, ["SUB"]):
        cookies = get_cookies(".weibo.cn", "WEIBO_COOKIE")

    if has_cookies(cookies, ["SUB"]):
        try:
            results = await _search_native(query, cookies, max_results)
            if results:
                return results
        except Exception as exc:
            print(f"[weibo] native failed: {exc}", file=sys.stderr)

    from channels._engines.baidu import search_baidu

    return await search_baidu(query, site="weibo.com", max_results=max_results)


async def _search_native(
    query: str, cookies: dict[str, str], max_results: int
) -> list[dict]:
    from channels._engines.cookie_auth import cookie_header
    from lib.search_runner import DEFAULT_TIMEOUT, make_result

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            "https://m.weibo.cn/api/container/getIndex",
            params={
                "containerid": f"100103type=1&q={query}",
                "page_type": "searchall",
                "page": 1,
            },
            headers={
                "User-Agent": _UA_MOBILE,
                "Cookie": cookie_header(cookies),
                "Referer": "https://m.weibo.cn/",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if resp.is_error:
            return []
        data = resp.json()
        if data.get("ok") != 1:
            return []

        cards = data.get("data", {}).get("cards", [])
        results: list[dict] = []
        for card in cards:
            mblogs = []
            if card.get("card_type") == 9:
                mb = card.get("mblog")
                if mb:
                    mblogs.append(mb)
            elif card.get("card_group"):
                for sub in card["card_group"]:
                    mb = sub.get("mblog")
                    if mb:
                        mblogs.append(mb)

            for mblog in mblogs:
                mid = mblog.get("id", mblog.get("mid", ""))
                if not mid:
                    continue
                text = re.sub(r"<[^>]+>", " ", str(mblog.get("text", "")))
                text = re.sub(r"\s+", " ", text).strip()
                if not text:
                    continue

                user = mblog.get("user", {}) or {}
                uid = user.get("id", "")
                url = (
                    f"https://weibo.com/{uid}/{mid}"
                    if uid
                    else f"https://m.weibo.cn/detail/{mid}"
                )

                metadata: dict = {"extracted_content": text[:3000]}
                if user.get("screen_name"):
                    metadata["author"] = user["screen_name"]
                for field, key in [
                    ("reposts_count", "reposts"),
                    ("comments_count", "num_comments"),
                    ("attitudes_count", "likes"),
                ]:
                    val = mblog.get(field)
                    if val is not None:
                        metadata[key] = val

                created_at = mblog.get("created_at", "")
                if created_at:
                    try:
                        from datetime import datetime, timezone

                        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                        metadata["published_at"] = dt.astimezone(
                            timezone.utc
                        ).isoformat()
                    except (ValueError, TypeError):
                        pass

                results.append(
                    make_result(
                        url=url,
                        title=text[:80],
                        snippet=text[:300],
                        source="weibo",
                        query=query,
                        extra_metadata=metadata,
                    )
                )
                if len(results) >= max_results:
                    return results
        return results
