from __future__ import annotations

import argparse
import importlib
import inspect
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

REPO = "https://github.com/jiangqqlmj/36Kr_Data_Crawler"
PLATFORM = "36kr"
PATH_ID = "36kr__jiangqqlmj_crawler"
WORKSPACE_REPO = Path("/tmp/as-matrix/36Kr_Data_Crawler")

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
        return " ".join(item.split())[:300]
    if not isinstance(item, dict):
        return " ".join(str(item).split())[:300]
    for key in ("title", "name", "desc", "description", "content", "text", "summary"):
        value = item.get(key)
        if value:
            return " ".join(str(value).split())[:300]
    return json.dumps(item, ensure_ascii=False)[:300]


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
    for key in ("data", "items", "result", "results", "list"):
        nested = value.get(key)
        if isinstance(nested, list):
            return nested
    return []


def _python_modules() -> list[str]:
    return sorted(
        {
            file.stem
            for file in WORKSPACE_REPO.rglob("*.py")
            if "__pycache__" not in file.parts
            and not file.name.startswith("test")
            and file.stem not in {"setup"}
            and len(file.relative_to(WORKSPACE_REPO).parts) <= 2
        }
    )


def _find_python_search_callable() -> tuple[Any | None, str | None]:
    candidate_modules = ["main", "crawler", "search", "spider"] + _python_modules()
    seen: set[str] = set()
    for module_name in candidate_modules:
        if module_name in seen:
            continue
        seen.add(module_name)
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        for attr_name in ("search", "query", "crawl", "fetch", "run"):
            func = getattr(module, attr_name, None)
            if callable(func):
                return func, f"{module_name}.{attr_name}"
    return None, None


def _invoke(func: Any, query: str) -> object:
    attempts = (
        ((), {"keyword": query}),
        ((), {"query": query}),
        ((query,), {}),
        ((), {}),
    )
    for args, kwargs in attempts:
        try:
            inspect.signature(func).bind_partial(*args, **kwargs)
        except TypeError:
            continue
        try:
            return func(*args, **kwargs)
        except TypeError:
            continue
    raise TypeError("sandbox_infeasible: could not call upstream Python entrypoint")


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        java_files = list(WORKSPACE_REPO.rglob("*.java"))
        python_callable, callable_name = _find_python_search_callable()
        if python_callable is None:
            if java_files or (WORKSPACE_REPO / "pom.xml").exists():
                raise RuntimeError("language_mismatch: jvm_required")
            raise RuntimeError("sandbox_infeasible: no Python search entrypoint found")

        response = _invoke(python_callable, query)
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
            note=f"Search callable used: {callable_name}",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if shutil.which("java") is None and WORKSPACE_REPO.exists():
            message = f"RuntimeError: language_mismatch: jvm_required ({exc})"
        else:
            message = f"{type(exc).__name__}: {exc}"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
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
