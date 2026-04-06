"""36kr native search via gateway API + article content from initialState.

2-step: GET CSRF token → POST gateway search.
Article content from window.initialState in article pages.
Verified: search 20 results/page, article content 1400-4384 chars.
WAF-sensitive — falls back to Baidu Kaifa when blocked.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import sys
import time

import httpx

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
_CSRF_URL = "https://36kr.com/pp/api/csrf"
_SEARCH_URL = "https://gateway.36kr.com/api/mis/nav/search/resultbytype"
_MAX_CONTENT_FETCH = 3


async def search(query: str, max_results: int = 10) -> list[dict]:
    try:
        results = await _search_native(query, max_results)
        if results:
            return results
    except Exception as exc:
        print(
            f"[36kr] native API failed, falling back to Baidu: {exc}", file=sys.stderr
        )

    from channels._engines.ddgs import search_ddgs_site

    return await search_ddgs_site(query, "36kr.com", max_results=max_results)


async def _search_native(query: str, max_results: int) -> list[dict]:
    from lib.search_runner import DEFAULT_TIMEOUT, make_result

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        csrf = await _get_csrf(client)
        if not csrf:
            return []

        ts = int(time.time() * 1000)
        page_cb = base64.b64encode(
            json.dumps(
                {
                    "firstId": 1,
                    "lastId": 1,
                    "firstCreateTime": ts,
                    "lastCreateTime": ts,
                }
            ).encode()
        ).decode()

        resp = await client.post(
            _SEARCH_URL,
            json={
                "param": {
                    "pageCallback": page_cb,
                    "pageEvent": 1,
                    "pageSize": max_results,
                    "platformId": 2,
                    "searchType": "article",
                    "searchWord": query,
                    "siteId": 1,
                    "sort": "date",
                },
                "partner_id": "web",
                "timestamp": ts,
            },
            headers={
                "User-Agent": _UA,
                "Content-Type": "application/json",
                "Referer": "https://36kr.com/",
                "Origin": "https://36kr.com",
                "M-X-XSRF-TOKEN": csrf,
                "Cookie": f"M-XSRF-TOKEN={csrf}",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            return []

        items = data.get("data", {}).get("itemList", [])
        if not items:
            return []

        results: list[dict] = []
        content_targets: list[tuple[int, str]] = []

        for item in items:
            item_id = str(item.get("itemId", "") or "")
            title = re.sub(
                r"</?em>", "", str(item.get("widgetTitle", "") or "")
            ).strip()
            if not item_id or not title:
                continue

            url = f"https://36kr.com/p/{item_id}"
            summary = str(item.get("summary", "") or "").strip()

            metadata: dict = {}
            pub_time = item.get("publishTime")
            if pub_time:
                try:
                    from datetime import datetime, timezone

                    dt = datetime.fromtimestamp(int(pub_time) / 1000, tz=timezone.utc)
                    metadata["published_at"] = dt.isoformat()
                except (ValueError, TypeError, OSError):
                    pass

            author = item.get("authorName") or item.get("author", "")
            if author:
                metadata["author"] = str(author)

            results.append(
                make_result(
                    url=url,
                    title=title,
                    snippet=summary or title,
                    source="36kr",
                    query=query,
                    extra_metadata=metadata,
                )
            )
            if len(content_targets) < _MAX_CONTENT_FETCH:
                content_targets.append((len(results) - 1, url))
            if len(results) >= max_results:
                break

        # Parallel article content fetch
        if content_targets:
            tasks = [_fetch_article(client, u) for _, u in content_targets]
            contents = await asyncio.gather(*tasks, return_exceptions=True)
            for (idx, _), content in zip(content_targets, contents, strict=True):
                if isinstance(content, str) and content:
                    results[idx].setdefault("metadata", {})["extracted_content"] = (
                        content
                    )

        return results


async def _get_csrf(client: httpx.AsyncClient) -> str:
    try:
        resp = await client.get(_CSRF_URL, headers={"User-Agent": _UA})
        for name, value in resp.cookies.items():
            if "xsrf" in name.lower():
                return value
    except Exception as exc:
        print(f"[36kr] CSRF failed: {exc}", file=sys.stderr)
    return ""


async def _fetch_article(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(url, headers={"User-Agent": _UA}, follow_redirects=True)
        if resp.is_error:
            return ""
        html = resp.text
        idx = html.find("window.initialState=")
        if idx == -1:
            return ""
        end = html.find("</script>", idx)
        if end == -1:
            return ""
        raw = html[idx + len("window.initialState=") : end].rstrip(";").strip()
        state = json.loads(raw)
        content = (
            state.get("articleDetail", {})
            .get("articleDetailData", {})
            .get("data", {})
            .get("widgetContent", "")
        )
        if not content:
            return ""
        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000] if len(text) > 100 else ""
    except Exception as exc:
        print(f"[36kr] article fetch: {exc}", file=sys.stderr)
        return ""
