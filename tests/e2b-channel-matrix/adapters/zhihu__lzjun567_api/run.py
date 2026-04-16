from __future__ import annotations

import argparse
import html
import importlib
import inspect
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO = "https://github.com/lzjun567/zhihu-api"
PLATFORM = "zhihu"
PATH_ID = "zhihu__lzjun567_api"
WORKSPACE_REPO = Path("/tmp/as-matrix/zhihu-api")

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


def _status_from_error(message: str) -> str:
    lowered = message.lower()
    if any(token in lowered for token in ("timeout", "timed out")):
        return "timeout"
    if any(
        token in lowered
        for token in ("captcha", "验证码", "403", "429", "access denied", "forbidden")
    ):
        return "anti_bot"
    if any(
        token in lowered
        for token in ("login", "cookie", "token", "unauthorized", "401")
    ):
        return "needs_login"
    return "error"


def _clean_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return _clean_text(item)
    if not isinstance(item, dict):
        return _clean_text(item)

    for key in (
        "title",
        "name",
        "excerpt",
        "description",
        "content",
        "text",
        "headline",
        "summary",
        "snippet",
    ):
        value = item.get(key)
        if value:
            return _clean_text(value)[:300]

    return _clean_text(json.dumps(item, ensure_ascii=False))[:300]


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


def _collect_items(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []

    items: list[object] = []
    for key in (
        "data",
        "items",
        "result",
        "results",
        "search",
        "search_result",
        "list",
    ):
        nested = value.get(key)
        if isinstance(nested, list):
            items.extend(nested)
    return items


def _call_search_callable(func: Callable[..., Any], query: str) -> object:
    attempts = (
        ((), {"query": query, "limit": 20}),
        ((), {"keyword": query, "limit": 20}),
        ((), {"q": query, "limit": 20}),
        ((query,), {"limit": 20}),
        ((query,), {}),
    )
    for args, kwargs in attempts:
        try:
            signature = inspect.signature(func)
        except (TypeError, ValueError):
            signature = None

        if signature is not None:
            try:
                signature.bind_partial(*args, **kwargs)
            except TypeError:
                continue

        try:
            return func(*args, **kwargs)
        except TypeError:
            continue

    raise TypeError("Could not find a compatible way to call search()")


def _find_search_callable() -> tuple[Callable[..., Any] | None, str | None]:
    module_names = ("zhihu", "zhihu.models")
    attr_names = ("search", "search_v3", "search_api")

    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        for attr_name in attr_names:
            func = getattr(module, attr_name, None)
            if callable(func):
                return func, f"{module_name}.{attr_name}"

        session_class = getattr(module, "Zhihu", None)
        if inspect.isclass(session_class):
            try:
                session = session_class()
            except Exception:
                continue
            method = getattr(session, "search", None)
            if callable(method):
                return method, f"{module_name}.Zhihu.search"

    return None, None


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

    try:
        search_callable, callable_name = _find_search_callable()
        if search_callable is None:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="empty",
                items_returned=0,
                avg_content_len=0,
                sample=None,
                note="No search entrypoint exposed by lzjun567/zhihu-api",
            )

        response = _call_search_callable(search_callable, query)
        items = _collect_items(response)
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
            note=f"Search callable used: {callable_name}",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        error = f"{type(exc).__name__}: {exc}"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=_status_from_error(error),
            error=error,
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
