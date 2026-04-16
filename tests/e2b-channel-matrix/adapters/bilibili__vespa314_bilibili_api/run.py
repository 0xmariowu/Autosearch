from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import sys
import time
from pathlib import Path

REPO = "https://github.com/Vespa314/bilibili-api"
PLATFORM = "bilibili"
PATH_ID = "bilibili__vespa314_bilibili_api"
WORKSPACE_REPO = Path("/tmp/as-matrix/bilibili-api-vespa314")

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
        "text",
        "name",
    ):
        value = item.get(key)
        if value:
            return str(value)
    return json.dumps(item, ensure_ascii=False)[:300]


def _summarize_items(items: list[object]) -> tuple[int, int, str | None]:
    limited_items = list(items[:20])
    if not limited_items:
        return 0, 0, None
    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = " ".join(texts[0].split())[:200]
    return len(limited_items), avg_len, sample or None


def _normalize_items(response: object) -> list[object]:
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return []

    content_types = {"video", "article", "bili_user", "media_bangumi", "media_ft"}
    groups = response.get("result")
    if isinstance(groups, list):
        items: list[object] = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            if group.get("result_type") in content_types:
                data = group.get("data")
                if isinstance(data, list):
                    items.extend(data)
        if items:
            return items

    for key in ("items", "data", "result", "results", "list"):
        value = response.get(key)
        if isinstance(value, list):
            return value
    return []


def _load_search_module() -> object:
    errors: list[str] = []
    for module_name in ("bilibili_api.search", "bilibili_api.utils.search"):
        try:
            return importlib.import_module(module_name)
        except Exception as exc:
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
    raise ImportError("; ".join(errors) or "search module not found")


async def _call_candidate(func: object, kwargs: dict[str, object]) -> object:
    result = func(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def _invoke_search(search_module: object, query: str) -> object:
    candidates: list[tuple[str, dict[str, object]]] = [
        ("search", {"keyword": query}),
        ("search", {"query": query}),
        ("search_by_type", {"keyword": query, "search_type": "video"}),
        ("search_by_type", {"query": query, "search_type": "video"}),
    ]
    last_error: Exception | None = None
    for func_name, kwargs in candidates:
        func = getattr(search_module, func_name, None)
        if func is None:
            continue
        try:
            return await _call_candidate(func, kwargs)
        except TypeError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise AttributeError("sandbox_infeasible: upstream search entrypoint not found")


async def _run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        search_module = _load_search_module()
        response = await _invoke_search(search_module, query)
        items = _normalize_items(response)
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
        lower = message.lower()
        status = "error"
        anti_bot_signals: list[str] = []
        if any(token in lower for token in ("403", "access denied", "forbidden")):
            status = "anti_bot"
            anti_bot_signals.append("403")
        elif "timeout" in lower:
            status = "timeout"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=status,
            error=message,
            anti_bot_signals=anti_bot_signals,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    args = parser.parse_args()

    print(json.dumps(asyncio.run(_run(args.query, args.query_category)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
