from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import httpx

REPO = "https://www.infoq.cn/feed"
PLATFORM = "infoq_cn"
PATH_ID = "infoq_cn__rss"
FEED_URL = "https://www.infoq.cn/feed"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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
    text = str(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return _clean_text(item)
    if not hasattr(item, "get"):
        return _clean_text(item)

    for key in (
        "summary",
        "title",
        "content",
        "snippet",
        "description",
        "text",
    ):
        value = item.get(key)
        if value:
            if isinstance(value, list):
                joined = " ".join(_clean_text(part.get("value", part)) for part in value)
                if joined:
                    return joined
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


def _ddgs_fallback(query: str) -> list[object]:
    if importlib.util.find_spec("ddgs") is None:
        raise ImportError("No module named 'ddgs'")

    script = """
import json
from ddgs import DDGS
with DDGS() as ddgs:
    items = list(ddgs.text(sys.argv[1], max_results=10) or [])
print(json.dumps(items, ensure_ascii=False))
"""
    proc = subprocess.run(
        [sys.executable, "-c", "import sys\n" + script, f"site:infoq.cn {query}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"ddgs exit {proc.returncode}")
    return json.loads(proc.stdout or "[]")


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _parse_xml_feed(content: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(content)
    entries: list[dict[str, str]] = []
    for element in root.iter():
        name = _local_name(element.tag)
        if name not in {"item", "entry"}:
            continue

        record: dict[str, str] = {}
        for child in list(element):
            child_name = _local_name(child.tag)
            if child_name in {"title", "summary", "description"}:
                record[child_name] = _clean_text(child.text or "")
        entries.append(record)
    return entries


def _parse_feed_content(content: bytes) -> list[object]:
    try:
        import feedparser

        feed = feedparser.parse(content)
        entries = list(getattr(feed, "entries", []) or [])
        if entries:
            return entries
        if getattr(feed, "bozo", 0):
            bozo_exc = getattr(feed, "bozo_exception", None)
            raise RuntimeError(str(bozo_exc or "feed parse failed"))
    except ModuleNotFoundError:
        pass
    return _parse_xml_feed(content)


def _feed_items(query: str) -> tuple[list[object], list[str], int | None]:
    headers = {"User-Agent": USER_AGENT}
    signals: list[str] = []
    status_code: int | None = None

    try:
        head = httpx.head(
            FEED_URL,
            headers=headers,
            follow_redirects=True,
            timeout=10.0,
            trust_env=False,
        )
        status_code = head.status_code
        if head.status_code == 404:
            signals.append("http_404")
            return [], signals, status_code
    except httpx.HTTPError:
        pass

    response = httpx.get(
        FEED_URL,
        headers=headers,
        follow_redirects=True,
        timeout=10.0,
        trust_env=False,
    )
    status_code = response.status_code
    if response.status_code == 404:
        signals.append("http_404")
        return [], signals, status_code
    response.raise_for_status()

    entries = _parse_feed_content(response.content)

    needle = query.casefold()
    matched = []
    for entry in entries:
        haystack = " ".join(
            _clean_text(entry.get(key, "")) for key in ("title", "summary")
        ).casefold()
        if needle in haystack:
            matched.append(entry)

    return matched, signals, status_code


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        matched, signals, status_code = _feed_items(query)
        if matched:
            items_returned, avg_content_len, sample = _summarize_items(matched, max_items=20)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="ok",
                items_returned=items_returned,
                avg_content_len=avg_content_len,
                sample=sample,
                anti_bot_signals=signals,
            )
        if status_code not in (None, 200):
            raise RuntimeError(f"HTTP {status_code}")

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="empty",
            items_returned=0,
            avg_content_len=0,
            sample=None,
            anti_bot_signals=signals,
        )
    except Exception as exc:
        if isinstance(exc, RuntimeError) and "HTTP " in str(exc):
            try:
                items = _ddgs_fallback(query)
                items_returned, avg_content_len, sample = _summarize_items(
                    items, max_items=10
                )
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
            except Exception:
                pass

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
