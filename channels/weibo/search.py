"""Weibo search: auto-cookie → hot search → Baidu fallback.

With SUB cookie (login): m.weibo.cn keyword search + full posts.
Without cookie: auto visitor passport + weibo.com/ajax/side/hotSearch
(50 trending items, zero user config needed). Query used to filter hot items.
Last resort: Baidu Kaifa site:weibo.com (URL-filtered).
"""

from __future__ import annotations

import json
import re
import sys

import httpx

_UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
_UA_DESKTOP = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


async def search(query: str, max_results: int = 10) -> list[dict]:
    from channels._engines.cookie_auth import get_cookies, has_cookies

    # Path 1: Login cookie → keyword search
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

    # Path 2: Visitor passport + hot search (zero config)
    try:
        results = await _search_hot(query, max_results)
        if results:
            return results
    except Exception as exc:
        print(f"[weibo] hot search failed: {exc}", file=sys.stderr)

    # Path 3: Baidu fallback
    from channels._engines.baidu import search_baidu

    return await search_baidu(query, site="weibo.com", max_results=max_results)


async def _get_visitor_cookies(client: httpx.AsyncClient) -> str:
    """Auto-obtain visitor SUB/SUBP via passport — zero user interaction."""
    r1 = await client.post(
        "https://passport.weibo.com/visitor/genvisitor",
        data={"cb": "gen_callback", "fp": '{"os":"1","browser":"Chrome135"}'},
        headers={"User-Agent": _UA_DESKTOP},
    )
    js = json.loads(r1.text.split("gen_callback(", 1)[1].rsplit(")", 1)[0])
    tid = js["data"]["tid"]

    r2 = await client.get(
        "https://passport.weibo.com/visitor/visitor",
        params={
            "a": "incarnate",
            "t": tid,
            "w": 2,
            "c": "095",
            "cb": "cross_domain",
            "from": "weibo",
        },
        headers={"User-Agent": _UA_DESKTOP},
    )
    js2 = json.loads(r2.text.split("cross_domain(", 1)[1].rsplit(")", 1)[0])
    sub = js2["data"]["sub"]
    subp = js2["data"].get("subp", "")
    parts = [f"SUB={sub}"]
    if subp:
        parts.append(f"SUBP={subp}")
    return "; ".join(parts)


async def _search_hot(query: str, max_results: int) -> list[dict]:
    """Fetch weibo hot search, filter by query relevance."""
    from lib.search_runner import DEFAULT_TIMEOUT, make_result

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT, follow_redirects=True
    ) as client:
        visitor_cookie = await _get_visitor_cookies(client)

        resp = await client.get(
            "https://weibo.com/ajax/side/hotSearch",
            headers={"User-Agent": _UA_DESKTOP, "Cookie": visitor_cookie},
        )
        if resp.is_error:
            return []

        data = resp.json()
        if data.get("ok") != 1:
            return []

        items = data.get("data", {}).get("realtime", [])
        if not items:
            return []

        # Filter by query relevance: keep items that share tokens with query
        query_tokens = set(query.lower().split())
        results: list[dict] = []

        for item in items:
            word = str(item.get("word", "") or "").strip()
            if not word:
                continue

            # Relevance: any query token appears in the hot word, or vice versa
            word_lower = word.lower()
            relevant = (
                not query
                or any(t in word_lower for t in query_tokens)
                or any(t in query.lower() for t in word_lower.split())
            )

            # If query is empty or very generic, take all
            if not query.strip():
                relevant = True

            if not relevant:
                continue

            url = f"https://s.weibo.com/weibo?q=%23{word}%23"
            num = item.get("num", 0)
            label = item.get("label_name", "")

            metadata: dict = {
                "hot_value": num,
            }
            if label:
                metadata["label"] = label

            results.append(
                make_result(
                    url=url,
                    title=f"#{word}#",
                    snippet=f"微博热搜: {word} ({num:,}阅读)"
                    if num
                    else f"微博热搜: {word}",
                    source="weibo",
                    query=query,
                    extra_metadata=metadata,
                )
            )
            if len(results) >= max_results:
                break

        # If no relevant hot items found, return all hot items (still better than nothing)
        if not results and items and query.strip():
            for item in items[:max_results]:
                word = str(item.get("word", "") or "").strip()
                if not word:
                    continue
                url = f"https://s.weibo.com/weibo?q=%23{word}%23"
                results.append(
                    make_result(
                        url=url,
                        title=f"#{word}#",
                        snippet=f"微博热搜: {word}",
                        source="weibo",
                        query=query,
                        extra_metadata={"hot_value": item.get("num", 0)},
                    )
                )

        return results


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
