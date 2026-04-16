from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO = "https://github.com/ds19991999/csdn-spider"
PLATFORM = "csdn"
PATH_ID = "csdn__ds19991999_spider"
WORKSPACE_REPO = Path("/tmp/as-matrix/csdn-spider")

if str(WORKSPACE_REPO) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_REPO))


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
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return " ".join(text.split())


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return _clean_text(item)
    if not isinstance(item, dict):
        return _clean_text(item)
    for key in (
        "title",
        "articleTitle",
        "description",
        "summary",
        "snippet",
        "content",
        "text",
        "name",
    ):
        value = item.get(key)
        if value:
            return _clean_text(value)[:300]
    return _clean_text(json.dumps(item, ensure_ascii=False))[:300]


def _summarize_items(items: list[object]) -> tuple[int, int, str | None]:
    limited = list(items[:20])
    if not limited:
        return 0, 0, None
    texts = [_extract_item_text(item) for item in limited]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited), avg_len, sample or None


def _load_cookie_path() -> str | None:
    path_value = os.environ.get("AS_MATRIX_CSDN_COOKIE_PATH", "").strip() or os.environ.get(
        "CSDN_COOKIE_PATH", ""
    ).strip()
    if path_value:
        return path_value

    cookie_value = os.environ.get("AS_MATRIX_CSDN_COOKIE", "").strip() or os.environ.get(
        "CSDN_COOKIE", ""
    ).strip()
    if not cookie_value:
        return None

    cookie_path = WORKSPACE_REPO / ".as_matrix_cookie.txt"
    cookie_path.write_text(cookie_value, encoding="utf-8")
    return str(cookie_path)


def _find_callable(module: object) -> tuple[Any | None, str | None]:
    for attr_name in ("search", "query", "search_articles", "search_blog", "search_blogs"):
        func = getattr(module, attr_name, None)
        if callable(func):
            return func, attr_name
    return None, None


def _invoke(func: Any, query: str, cookie_path: str | None) -> object:
    attempts = [
        ((), {"keyword": query, "cookie_path": cookie_path}),
        ((), {"query": query, "cookie_path": cookie_path}),
        ((query, cookie_path), {}),
        ((query,), {}),
    ]
    for args, kwargs in attempts:
        clean_kwargs = {key: value for key, value in kwargs.items() if value is not None}
        try:
            inspect.signature(func).bind_partial(*args, **clean_kwargs)
        except TypeError:
            continue
        try:
            return func(*args, **clean_kwargs)
        except TypeError:
            continue
    raise TypeError("sandbox_infeasible: could not call upstream search function")


def _collect_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    items: list[object] = []
    for key in ("data", "items", "result", "results", "list", "articles"):
        value = payload.get(key)
        if isinstance(value, list):
            items.extend(value)
    return items


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        csdn_module = importlib.import_module("csdn")
        search_callable, callable_name = _find_callable(csdn_module)
        cookie_path = _load_cookie_path()

        if search_callable is None:
            spider = getattr(csdn_module, "spider", None)
            if callable(spider) and not cookie_path:
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
                        "needs_login: ds19991999/csdn-spider documents cookie.txt-backed "
                        "user-blog crawling via csdn.spider(user, cookie_path) and does not "
                        "expose a keyword-search callable without authenticated session material"
                    ),
                )
            raise RuntimeError("sandbox_infeasible: no keyword-search entrypoint exposed by csdn module")

        response = _invoke(search_callable, query, cookie_path)
        items = _collect_items(response)
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
            note=f"Search callable used: csdn.{callable_name}",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        lowered = message.lower()
        status = "error"
        if "needs_login" in lowered or "cookie" in lowered:
            status = "needs_login"
        elif "timeout" in lowered:
            status = "timeout"
        elif any(token in lowered for token in ("captcha", "403", "429", "forbidden")):
            status = "anti_bot"
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
    print(json.dumps(run(**vars(parser.parse_args())), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
