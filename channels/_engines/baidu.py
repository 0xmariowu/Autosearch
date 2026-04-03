from __future__ import annotations

import sys
from html import unescape

import httpx

# Baidu Kaifa (Developer Search) — no CAPTCHA, JSON API, supports site: filter
KAIFA_URL = "https://kaifa.baidu.com/rest/v1/search"

SITE_TO_SOURCE = {
    "zhihu.com": "zhihu",
    "csdn.net": "csdn",
    "juejin.cn": "juejin",
    "36kr.com": "36kr",
    "infoq.cn": "infoq-cn",
    "weibo.com": "weibo",
    "xueqiu.com": "xueqiu",
    "xiaoyuzhoufm.com": "xiaoyuzhou",
    "xiaohongshu.com": "xiaohongshu",
    "douyin.com": "douyin",
}


def _source_for_site(site: str | None) -> str:
    if not site:
        return "baidu"
    normalized = site.lower().removeprefix("www.")
    return SITE_TO_SOURCE.get(normalized, normalized.split(".", 1)[0])


async def search_baidu(
    query: str,
    site: str | None = None,
    max_results: int = 10,
) -> list[dict]:
    from lib.search_runner import DEFAULT_TIMEOUT, make_result

    full_query = f"site:{site} {query}" if site else query
    source = _source_for_site(site)

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                KAIFA_URL,
                params={
                    "wd": full_query,
                    "pageSize": max_results,
                    "pageNum": 1,
                    "paramList": f"page_num=1,page_size={max_results}",
                    "position": 0,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            docs = data.get("data", {}).get("documents", {}).get("data", [])
            if not docs:
                return []

            results: list[dict] = []
            for entry in docs:
                digest = entry.get("techDocDigest", {})
                title = unescape(str(digest.get("title", "") or "")).strip()
                url = str(digest.get("url", "") or "").strip()
                if not title or not url:
                    continue

                snippet = unescape(str(digest.get("summary", "") or "")).strip()
                metadata: dict[str, str] = {}

                results.append(
                    make_result(
                        url=url,
                        title=title,
                        snippet=snippet,
                        source=source,
                        query=full_query,
                        extra_metadata=metadata,
                    )
                )
                if len(results) >= max_results:
                    break

            return results

    except Exception as exc:
        print(f"[baidu-kaifa] search failed for {full_query!r}: {exc}", file=sys.stderr)
        return []
