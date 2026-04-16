from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time

import httpx

REPO = "https://so.csdn.net/api/v3/search"
PLATFORM = "csdn"
PATH_ID = "csdn__rss"
SEARCH_URL = "https://so.csdn.net/api/v3/search"
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
    if not isinstance(item, dict):
        return _clean_text(item)

    for key in (
        "title",
        "description",
        "summary",
        "snippet",
        "body",
        "content",
        "articleTitle",
        "articleDescription",
    ):
        value = item.get(key)
        if value:
            return _clean_text(value)

    return _clean_text(json.dumps(item, ensure_ascii=False))


def _has_real_content(item: object) -> bool:
    return bool(_extract_item_text(item).strip())


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


def _collect_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        return [item for item in payload if _has_real_content(item)]
    if not isinstance(payload, dict):
        return []

    items: list[object] = []
    for key in ("result_vos", "result", "list", "items", "data", "documents"):
        value = payload.get(key)
        if isinstance(value, list):
            items.extend(value)
        elif isinstance(value, dict):
            items.extend(_collect_items(value))
    return [item for item in items if _has_real_content(item)]


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
        [sys.executable, "-c", "import sys\n" + script, f"site:csdn.net {query}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"ddgs exit {proc.returncode}")
    return json.loads(proc.stdout or "[]")


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        response = httpx.get(
            SEARCH_URL,
            params={"q": query, "t": "all"},
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
            },
            follow_redirects=True,
            timeout=10.0,
            trust_env=False,
        )

        if response.status_code // 100 == 2:
            payload = response.json()
            items = _collect_items(payload)
            if items:
                items_returned, avg_content_len, sample = _summarize_items(
                    items, max_items=20
                )
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                return _result_payload(
                    query,
                    query_category,
                    elapsed_ms,
                    status="ok",
                    items_returned=items_returned,
                    avg_content_len=avg_content_len,
                    sample=sample,
                )

        try:
            items = _ddgs_fallback(query)
            items_returned, avg_content_len, sample = _summarize_items(items, max_items=10)
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
        except ImportError:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            code = response.status_code
            if response.status_code // 100 == 2:
                return _result_payload(
                    query,
                    query_category,
                    elapsed_ms,
                    status="error",
                    error=f"HTTP {code}: empty response",
                )
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="error",
                error=f"HTTP {code}",
            )
    except httpx.TimeoutException as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="timeout",
            error=f"{type(exc).__name__}: {exc}",
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
