from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from html import unescape

import httpx

BAIDU_SEARCH_URL = "https://www.baidu.com/s"
CAPTCHA_PATH = "wappass.baidu.com/static/captcha"
RESULTS_PER_PAGE = 10
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)

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
}


def _source_for_site(site: str | None) -> str:
    if not site:
        return "baidu"

    normalized = site.lower().removeprefix("www.")
    return SITE_TO_SOURCE.get(normalized, normalized.split(".", 1)[0])


def _published_at(entry: dict) -> str | None:
    raw_timestamp = entry.get("time")
    if raw_timestamp in (None, ""):
        return None

    try:
        timestamp = int(raw_timestamp)
    except (TypeError, ValueError):
        return None

    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _parse_general_results(
    payload: dict,
    *,
    make_result,
    source: str,
    query: str,
) -> list[dict]:
    feed = payload.get("feed", {})
    entries = feed.get("entry")
    if entries is None:
        raise ValueError("invalid Baidu response: missing feed.entry")
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        raise ValueError("invalid Baidu response: unexpected feed.entry type")

    results: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        title = unescape(str(entry.get("title", "") or "")).strip()
        url = str(entry.get("url", "") or "").strip()
        if not title or not url:
            continue

        snippet = unescape(str(entry.get("abs", "") or "")).strip()
        metadata: dict[str, str] = {}
        published_at = _published_at(entry)
        if published_at:
            metadata["published_at"] = published_at

        results.append(
            make_result(
                url=url,
                title=title,
                snippet=snippet,
                source=source,
                query=query,
                extra_metadata=metadata,
            )
        )

    return results


async def search_baidu(
    query: str,
    site: str | None = None,
    max_results: int = 10,
) -> list[dict]:
    from autosearch.v2.search_runner import DEFAULT_TIMEOUT, make_result

    full_query = f"site:{site} {query}" if site else query
    source = _source_for_site(site)
    target_results = max(1, max_results)
    total_pages = max(1, (target_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)
    results: list[dict] = []

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=False,
        ) as client:
            for page_index in range(total_pages):
                response = await client.get(
                    BAIDU_SEARCH_URL,
                    params={
                        "wd": full_query,
                        "rn": RESULTS_PER_PAGE,
                        "pn": page_index * RESULTS_PER_PAGE,
                        "tn": "json",
                    },
                )
                response.raise_for_status()

                location = response.headers.get("Location", "")
                if CAPTCHA_PATH in location:
                    raise RuntimeError("Baidu returned a captcha redirect")

                payload = json.loads(response.text, strict=False)
                page_results = _parse_general_results(
                    payload,
                    make_result=make_result,
                    source=source,
                    query=full_query,
                )
                if not page_results:
                    break

                results.extend(page_results)
                if len(results) >= target_results:
                    return results[:target_results]

        return results[:target_results]
    except Exception as exc:
        print(f"[baidu] search failed for {full_query!r}: {exc}", file=sys.stderr)
        return []
