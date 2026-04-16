from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "https://github.com/rachelos/we-mp-rss"
WORKSPACE_REPO = Path("/tmp/as-matrix/we-mp-rss")
if str(WORKSPACE_REPO) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_REPO))


def _result_payload(
    query: str, query_category: str, elapsed_ms: int, **extra: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "platform": "wechat",
        "path_id": "wechat__we_mp_rss",
        "repo": REPO,
        "query": query,
        "query_category": query_category,
        "total_ms": elapsed_ms,
        "anti_bot_signals": [],
    }
    payload.update(extra)
    return payload


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)
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
            return str(value)
    return json.dumps(item, ensure_ascii=False)[:300]


def _summarize_items(items: list[object]) -> tuple[int, int, str | None]:
    limited_items = items[:20]
    if not limited_items:
        return 0, 0, None
    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = " ".join(texts[0].split())[:200]
    return len(limited_items), avg_len, sample or None


def _normalize_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in (
        "items",
        "data",
        "list",
        "records",
        "feeds",
        "articles",
        "result",
        "results",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _normalize_items(value)
            if nested:
                return nested
    return []


def _probe_instance(base_url: str, query: str) -> list[object]:
    base = base_url.rstrip("/")
    openapi_url = f"{base}/openapi.json"
    with urllib.request.urlopen(openapi_url, timeout=10) as response:
        document = json.loads(response.read().decode("utf-8"))

    paths = document.get("paths") if isinstance(document, dict) else {}
    if not isinstance(paths, dict):
        return []

    for path, methods in paths.items():
        if not isinstance(methods, dict) or "get" not in methods:
            continue
        path_lower = path.lower()
        if not any(
            token in path_lower
            for token in ("rss", "feed", "article", "search", "sub", "wechat")
        ):
            continue

        parameters = methods.get("get", {}).get("parameters") or []
        if not isinstance(parameters, list):
            parameters = []

        query_params: dict[str, str | int] = {}
        names = {
            str(param.get("name"))
            for param in parameters
            if isinstance(param, dict) and param.get("name")
        }
        for candidate in ("keyword", "query", "name", "title", "q"):
            if candidate in names:
                query_params[candidate] = query
                break
        for candidate in ("limit", "size", "page_size", "per_page"):
            if candidate in names:
                query_params[candidate] = 20
                break

        target = urllib.parse.urljoin(f"{base}/", path.lstrip("/"))
        if query_params:
            target = f"{target}?{urllib.parse.urlencode(query_params)}"

        with urllib.request.urlopen(target, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return _normalize_items(payload)

    return []


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    if not WORKSPACE_REPO.exists():
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error="Repository not found; run setup.sh first",
        )

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
                "Set WE_MP_RSS_URL to a hosted we-mp-rss instance. The upstream "
                "project requires service deployment plus an authenticated "
                "account/session before article data is available."
            ),
        )

    try:
        items = _probe_instance(base_url, query)
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
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"HTTPError: {exc.code} {exc.reason}"
        status = "needs_login" if exc.code in {401, 403} else "error"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=status,
            error=message,
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
