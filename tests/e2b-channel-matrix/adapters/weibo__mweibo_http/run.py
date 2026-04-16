from __future__ import annotations

import argparse
import html
import json
import re
import time
from urllib.parse import quote

REPO = "https://m.weibo.cn/"
PLATFORM = "weibo"
PATH_ID = "weibo__mweibo_http"
SEARCH_ENDPOINT = (
    "https://m.weibo.cn/api/container/getIndex?containerid=100103type=1&q={query}"
)


def _result_payload(
    query: str, query_category: str, elapsed_ms: int, **extra: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "platform": PLATFORM,
        "path_id": PATH_ID,
        "repo": REPO,
        "query": query,
        "query_category": query_category,
        "total_ms": elapsed_ms,
        "anti_bot_signals": [],
    }
    payload.update(extra)
    return payload


def _clean_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    for key in (
        "content",
        "snippet",
        "body",
        "description",
        "summary",
        "title",
        "text",
    ):
        value = item.get(key)
        if value:
            return _clean_text(value)

    return _clean_text(json.dumps(item, ensure_ascii=False))


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = " ".join(texts[0].split())[:200]
    return len(limited_items), avg_len, sample or None


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    try:
        import httpx

        encoded_query = quote(query, safe="")
        url = SEARCH_ENDPOINT.format(query=encoded_query)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
                "Mobile/15E148 Safari/604.1"
            ),
            "Referer": "https://m.weibo.cn/",
            "Accept": "application/json, text/plain, */*",
        }
        response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        payload = response.json()

        cards = payload.get("data", {}).get("cards") or []
        items: list[dict[str, object]] = []
        for card in cards:
            if not isinstance(card, dict):
                continue
            mblog = card.get("mblog")
            if not isinstance(mblog, dict):
                continue

            mblog_id = mblog.get("id")
            if not mblog_id:
                continue

            user = mblog.get("user") or {}
            screen_name = (
                user.get("screen_name") if isinstance(user, dict) else None
            ) or ""
            text = _clean_text(mblog.get("text") or "")
            created_at = mblog.get("created_at")
            items.append(
                {
                    "title": screen_name or text,
                    "text": text,
                    "author": screen_name or None,
                    "published_at": created_at,
                    "url": f"https://m.weibo.cn/status/{mblog_id}",
                    "id": str(mblog_id),
                }
            )

        items_returned, avg_content_len, sample = _summarize_items(items, max_items=20)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="ok" if items_returned else "empty",
            items_returned=items_returned,
            avg_content_len=avg_content_len,
            sample=sample,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    args = parser.parse_args()

    payload = run(args.query, args.query_category)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
