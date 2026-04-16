from __future__ import annotations

import argparse
import json
import time

REPO = "https://github.com/deedy5/ddgs"


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    for key in ("body", "snippet", "description", "summary", "title", "text"):
        value = item.get(key)
        if value:
            return str(value)

    return json.dumps(item, ensure_ascii=False)


def _summarize_items(
    items: list[object], max_items: int = 10
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = " ".join(texts[0].split())[:200]
    return len(limited_items), avg_len, sample or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    args = parser.parse_args()

    started = time.perf_counter()
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            items = list(
                ddgs.text(f"{args.query} site:bilibili.com", max_results=10) or []
            )

        items_returned, avg_content_len, sample = _summarize_items(items, max_items=10)
        payload = {
            "platform": "seo",
            "path_id": "seo__bing_via_ddgs",
            "repo": REPO,
            "query": args.query,
            "query_category": args.query_category,
            "status": "ok" if items_returned else "empty",
            "items_returned": items_returned,
            "avg_content_len": avg_content_len,
            "total_ms": int((time.perf_counter() - started) * 1000),
            "sample": sample,
            "anti_bot_signals": [],
        }
    except Exception as exc:
        payload = {
            "platform": "seo",
            "path_id": "seo__bing_via_ddgs",
            "repo": REPO,
            "query": args.query,
            "query_category": args.query_category,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "total_ms": int((time.perf_counter() - started) * 1000),
            "anti_bot_signals": [],
        }

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
