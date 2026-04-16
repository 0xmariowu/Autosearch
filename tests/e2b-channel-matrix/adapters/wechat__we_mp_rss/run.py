from __future__ import annotations

import argparse
import json
import os
import re
import time

REPO = "https://github.com/rachelos/we-mp-rss"
PLATFORM = "wechat"
PATH_ID = "wechat__we_mp_rss"


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

    for key in (
        "content",
        "desc",
        "description",
        "summary",
        "snippet",
        "title",
        "name",
        "text",
    ):
        value = item.get(key)
        if value:
            return _clean_text(value)
    return _clean_text(json.dumps(dict(item), ensure_ascii=False))


def _summarize_items(items: list[object]) -> tuple[int, int, str | None]:
    limited_items = items[:20]
    if not limited_items:
        return 0, 0, None
    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited_items), avg_len, sample or None


def _load_entries(feed_url: str) -> list[object]:
    import feedparser

    feed = feedparser.parse(feed_url)
    entries = list(getattr(feed, "entries", []) or [])
    if getattr(feed, "bozo", 0) and not entries:
        bozo_exc = getattr(feed, "bozo_exception", None)
        raise RuntimeError(str(bozo_exc or "feed parse failed"))
    return entries


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    base_url = os.environ.get("WE_MP_RSS_URL", "").strip()
    if not base_url:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="needs_login",
            items_returned=0,
            avg_content_len=0,
            sample=None,
            error=(
                "Set WE_MP_RSS_URL to a hosted we-mp-rss RSS endpoint. The upstream "
                "project requires service deployment plus an authenticated "
                "account/session before article data is available."
            ),
        )

    try:
        entries = _load_entries(base_url)
        needle = query.casefold()
        items = []
        for entry in entries:
            haystack = " ".join(
                _clean_text(entry.get(key, ""))
                for key in ("title", "summary", "description", "content")
            ).casefold()
            if needle in haystack:
                items.append(entry)

        items_returned, avg_content_len, sample = _summarize_items(items)
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
        message = f"{type(exc).__name__}: {exc}"
        status = "needs_login" if "unauthorized" in message.lower() else "error"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=status,
            error=message,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    args = parser.parse_args()

    print(json.dumps(run(args.query, args.query_category), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
