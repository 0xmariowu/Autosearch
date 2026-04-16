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

REPO = "https://github.com/SchrodingersBug/CSDN_SearchEngine"
PLATFORM = "csdn"
PATH_ID = "csdn__schrodingersbug_search"
WORKSPACE_REPO = Path("/tmp/as-matrix/CSDN_SearchEngine")

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
        "name",
        "summary",
        "description",
        "content",
        "snippet",
        "text",
        "articleTitle",
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


def _collect_items(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []

    items: list[object] = []
    for key in ("data", "items", "result", "results", "list", "documents", "docs"):
        nested = value.get(key)
        if isinstance(nested, list):
            items.extend(nested)
    return items


def _module_candidates() -> list[str]:
    candidates = ["main", "search", "crawler", "spider", "engine"]
    for file in WORKSPACE_REPO.rglob("*.py"):
        if "__pycache__" in file.parts or file.name.startswith("test"):
            continue
        relative = file.relative_to(WORKSPACE_REPO)
        if len(relative.parts) > 2:
            continue
        stem = relative.stem
        if stem == "__init__":
            continue
        candidates.append(".".join(relative.with_suffix("").parts))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _find_search_target() -> tuple[Any | None, str | None]:
    search_names = (
        "search",
        "query",
        "search_keyword",
        "search_engine",
        "fetch",
        "crawl",
    )
    method_names = ("search", "query", "fetch", "crawl")

    for module_name in _module_candidates():
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        for attr_name in search_names:
            func = getattr(module, attr_name, None)
            if callable(func):
                return func, f"{module_name}.{attr_name}"

        for name in dir(module):
            candidate = getattr(module, name, None)
            if not inspect.isclass(candidate):
                continue
            if not any(token in name.lower() for token in ("spider", "crawler", "search", "engine")):
                continue
            try:
                instance = candidate()
            except Exception:
                continue
            for method_name in method_names:
                method = getattr(instance, method_name, None)
                if callable(method):
                    return method, f"{module_name}.{name}.{method_name}"
    return None, None


def _invoke(target: Any, query: str) -> object:
    attempts = (
        ((), {"keyword": query}),
        ((), {"query": query}),
        ((), {"wd": query}),
        ((query,), {}),
        ((), {}),
    )
    for args, kwargs in attempts:
        try:
            inspect.signature(target).bind_partial(*args, **kwargs)
        except TypeError:
            continue
        try:
            return target(*args, **kwargs)
        except TypeError:
            continue
    raise TypeError("sandbox_infeasible: no compatible way to call upstream search target")


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        target, target_name = _find_search_target()
        if target is None:
            raise RuntimeError("sandbox_infeasible: no fetch/search callable found in upstream repo")

        response = _invoke(target, query)
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
            note=f"Upstream entry used: {target_name}",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        lowered = message.lower()
        status = "error"
        if "timeout" in lowered:
            status = "timeout"
        elif any(token in lowered for token in ("captcha", "403", "429", "forbidden")):
            status = "anti_bot"
        elif any(token in lowered for token in ("login", "cookie", "token", "unauthorized")):
            status = "needs_login"
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
