"""CSDN native search API + article content fetch.

Uses so.csdn.net/api/v3/search (public, no auth).
Verified: 24/25 tests passed across 5 query types.
Falls back to Baidu Kaifa on API failure.
"""

from __future__ import annotations

import asyncio
import re
import sys

import httpx

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
_SEARCH_URL = "https://so.csdn.net/api/v3/search"
_MAX_CONTENT_FETCH = 3
_CONTENT_PATTERNS = [
    re.compile(r'id="article_content"[^>]*>(.*?)</div>', re.DOTALL),
    re.compile(r'class="article_content"[^>]*>(.*?)</div>', re.DOTALL),
    re.compile(r'id="content_views"[^>]*>(.*?)</div>', re.DOTALL),
]


async def search(query: str, max_results: int = 10) -> list[dict]:

    try:
        results = await _search_native(query, max_results)
        if results:
            return results
    except Exception as exc:
        print(
            f"[csdn] native API failed, falling back to Baidu: {exc}", file=sys.stderr
        )

    from channels._engines.baidu import search_baidu

    return await search_baidu(query, site="csdn.net", max_results=max_results)


async def _search_native(query: str, max_results: int) -> list[dict]:
    from lib.search_runner import DEFAULT_TIMEOUT, make_result

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            _SEARCH_URL,
            params={"q": query, "t": "all", "p": 1, "s": 0, "tm": 0},
            headers={"User-Agent": _UA},
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("result_vos", [])
        if not items:
            return []

        results: list[dict] = []
        blog_urls: list[tuple[int, str]] = []

        for item in items:
            url = str(item.get("url", "") or "").strip()
            title = str(item.get("title", "") or "").strip()
            title = re.sub(r"</?em>", "", title)
            if not url or not title:
                continue

            snippet = str(item.get("description", "") or "").strip()
            snippet = re.sub(r"</?em>", "", snippet)

            metadata: dict = {}
            for field, key in [
                ("view_num", "views"),
                ("digg_num", "diggs"),
                ("comment_num", "comments"),
                ("nickname", "author"),
            ]:
                val = item.get(field)
                if val is not None:
                    metadata[key] = val

            create_time = item.get("create_time") or item.get("create_date", "")
            if create_time:
                ct = str(create_time)
                # Unix epoch seconds (e.g. 1744992000)
                if ct.isdigit() and len(ct) >= 10:
                    try:
                        from datetime import datetime, timezone

                        dt = datetime.fromtimestamp(int(ct[:10]), tz=timezone.utc)
                        metadata["published_at"] = dt.isoformat()
                    except (ValueError, OSError):
                        pass
                # ISO date string
                elif "-" in ct and len(ct) >= 10:
                    metadata["published_at"] = ct[:10] + "T00:00:00Z"

            results.append(
                make_result(
                    url=url,
                    title=title,
                    snippet=snippet,
                    source="csdn",
                    query=query,
                    extra_metadata=metadata,
                )
            )
            if "blog.csdn.net" in url and len(blog_urls) < _MAX_CONTENT_FETCH:
                blog_urls.append((len(results) - 1, url))
            if len(results) >= max_results:
                break

        # Parallel article content fetch
        if blog_urls:
            tasks = [_fetch_article(client, url) for _, url in blog_urls]
            contents = await asyncio.gather(*tasks, return_exceptions=True)
            for (idx, _), content in zip(blog_urls, contents, strict=True):
                if isinstance(content, str) and content:
                    results[idx].setdefault("metadata", {})["extracted_content"] = (
                        content
                    )

        return results


async def _fetch_article(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": _UA, "Referer": "https://so.csdn.net/"},
            follow_redirects=True,
        )
        if resp.is_error:
            return ""
        html = resp.text
        for pattern in _CONTENT_PATTERNS:
            match = pattern.search(html)
            if match:
                from html import unescape

                text = re.sub(r"<[^>]+>", " ", match.group(1))
                text = unescape(text)  # Decode &#xff08; etc.
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 100:
                    return text[:3000]
        return ""
    except Exception as exc:
        print(f"[csdn] article fetch: {exc}", file=sys.stderr)
        return ""
