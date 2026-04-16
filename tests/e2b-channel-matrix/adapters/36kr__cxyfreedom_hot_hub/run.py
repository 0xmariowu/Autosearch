from __future__ import annotations

import argparse
import importlib
import inspect
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO = "https://github.com/cxyfreedom/website-hot-hub"
PLATFORM = "36kr"
PATH_ID = "36kr__cxyfreedom_hot_hub"
WORKSPACE_REPO = Path("/tmp/as-matrix/website-hot-hub")

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
    if "timeout" in lowered:
        return "timeout"
    if any(token in lowered for token in ("captcha", "403", "429", "forbidden")):
        return "anti_bot"
    if any(token in lowered for token in ("login", "cookie", "token", "unauthorized")):
        return "needs_login"
    return "error"


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
        "name",
        "desc",
        "description",
        "content",
        "text",
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
    items: list[object] = []

    def visit(node: object) -> None:
        if isinstance(node, list):
            for child in node:
                visit(child)
            return

        if isinstance(node, dict):
            if any(key in node for key in ("title", "name", "desc", "description")):
                items.append(node)
            for child in node.values():
                visit(child)

    visit(value)
    return items


def _load_module() -> object:
    errors: list[str] = []
    for module_name in ("website_36kr", "website_hot_hub.website_36kr"):
        try:
            return importlib.import_module(module_name)
        except Exception as exc:
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
    raise ImportError("; ".join(errors) or "website_36kr import failed")


def _instantiate_client(module: object) -> object:
    for attr_name in ("WebSite36Kr", "Website36Kr", "Website36KR"):
        cls = getattr(module, attr_name, None)
        if inspect.isclass(cls):
            return cls()

    for name in dir(module):
        if "36" not in name.lower() or "kr" not in name.lower():
            continue
        candidate = getattr(module, name, None)
        if inspect.isclass(candidate):
            return candidate()

    raise AttributeError("sandbox_infeasible: no 36kr class found in website-hot-hub")


def _call_best_effort(target: object, query: str) -> object:
    attempts: list[tuple[str, dict[str, object]]] = [
        ("search", {"keyword": query}),
        ("search", {"query": query}),
        ("run", {"update_readme": False}),
        ("run", {}),
        ("get_data", {}),
        ("fetch_data", {}),
    ]
    last_error: Exception | None = None
    for name, kwargs in attempts:
        func = getattr(target, name, None)
        if not callable(func):
            continue
        try:
            inspect.signature(func).bind_partial(**kwargs)
        except TypeError:
            if kwargs:
                try:
                    inspect.signature(func).bind_partial()
                    kwargs = {}
                except TypeError:
                    continue
        try:
            return func(**kwargs)
        except TypeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise AttributeError("sandbox_infeasible: no callable run/search entrypoint found")


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    if not WORKSPACE_REPO.exists():
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error=f"Repository not found at {WORKSPACE_REPO}; run setup.sh first.",
        )

    try:
        module = _load_module()
        client = _instantiate_client(module)
        response = _call_best_effort(client, query)
        items = _collect_items(response)

        if not items:
            for attr_name in ("result", "results", "items", "top_data", "data"):
                value = getattr(client, attr_name, None)
                if value is not None:
                    items.extend(_collect_items(value))

        needle = query.casefold()
        matched = [item for item in items if needle in _extract_item_text(item).casefold()]
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
        message = f"{type(exc).__name__}: {exc}"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=_status_from_error(message),
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
