from __future__ import annotations

import argparse
import json
import re
import time

REPO = "https://www.infoq.cn/feed"
PLATFORM = "infoq_cn"
PATH_ID = "infoq_cn__rss"
FEED_URL = "https://www.infoq.cn/feed"


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
    text = str(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return _clean_text(item)
    if not hasattr(item, "get"):
        return _clean_text(item)

    for key in ("summary", "title", "content", "snippet", "description", "text"):
        value = item.get(key)
        if not value:
            continue
        if isinstance(value, list):
            joined = " ".join(_clean_text(part.get("value", part)) for part in value)
            if joined:
                return joined
            continue
        return _clean_text(value)

    return _clean_text(json.dumps(dict(item), ensure_ascii=False))


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited_items), avg_len, sample or None


def _load_entries() -> list[object]:
    import feedparser

    feed = feedparser.parse(FEED_URL)
    entries = list(getattr(feed, "entries", []) or [])
    if getattr(feed, "bozo", 0) and not entries:
        bozo_exc = getattr(feed, "bozo_exception", None)
        raise RuntimeError(str(bozo_exc or "feed parse failed"))
    return entries


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        entries = _load_entries()
        needle = query.casefold()
        matched = []
        for entry in entries:
            haystack = " ".join(
                _clean_text(entry.get(key, ""))
                for key in ("title", "summary", "description", "content")
            ).casefold()
            if needle in haystack:
                matched.append(entry)

        items_returned, avg_content_len, sample = _summarize_items(matched, max_items=20)
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
        status = "timeout" if "timeout" in str(exc).lower() else "error"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=status,
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
