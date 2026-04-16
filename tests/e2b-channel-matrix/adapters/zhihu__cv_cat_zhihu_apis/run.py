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

REPO = "https://github.com/cv-cat/ZhihuApis"
PLATFORM = "zhihu"
PATH_ID = "zhihu__cv_cat_zhihu_apis"
WORKSPACE_REPO = Path("/tmp/as-matrix/ZhihuApis")

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


def _status_from_message(message: str) -> str:
    lowered = message.lower()
    if "timeout" in lowered:
        return "timeout"
    if any(token in lowered for token in ("captcha", "403", "429", "forbidden", "x-zse")):
        return "anti_bot"
    if any(token in lowered for token in ("login", "cookie", "token", "401", "unauthorized")):
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
        "headline",
        "description",
        "content",
        "text",
        "summary",
        "snippet",
    ):
        value = item.get(key)
        if value:
            return _clean_text(value)[:300]
    if isinstance(item.get("object"), dict):
        return _extract_item_text(item["object"])
    return _clean_text(json.dumps(item, ensure_ascii=False))[:300]


def _summarize_items(items: list[object]) -> tuple[int, int, str | None]:
    limited_items = list(items[:20])
    if not limited_items:
        return 0, 0, None
    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited_items), avg_len, sample or None


def _filter_search_items(value: object) -> list[object]:
    results: list[object] = []

    def visit(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return

        obj = node.get("object")
        if isinstance(obj, dict):
            obj_type = str(obj.get("type") or "").lower()
            if obj_type in {"answer", "article"}:
                results.append(obj)

        node_type = str(node.get("type") or "").lower()
        if node_type in {"answer", "article"}:
            results.append(node)

        for child in node.values():
            visit(child)

    visit(value)
    return results


def _call_search(func: Callable[..., Any], query: str) -> object:
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
    raise TypeError("sandbox_infeasible: no compatible search() call signature found")


def _probe_upstream() -> tuple[Callable[..., Any] | None, str | None, bool]:
    saw_signer = False
    module_names = (
        "ZhihuApis",
        "zhihuapis",
        "zhihu_apis",
        "main",
        "app",
        "src",
    )
    search_names = ("search", "search_v3", "search_api", "search_by_keyword")
    sign_names = ("sign", "signer", "x_zse_96", "gen_signature", "generate_signature")

    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        for attr_name in sign_names:
            if callable(getattr(module, attr_name, None)):
                saw_signer = True

        for attr_name in search_names:
            func = getattr(module, attr_name, None)
            if callable(func):
                return func, f"{module_name}.{attr_name}", saw_signer

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if inspect.isclass(attr):
                for sign_name in sign_names:
                    if callable(getattr(attr, sign_name, None)):
                        saw_signer = True
                for search_name in search_names:
                    method = getattr(attr, search_name, None)
                    if callable(method):
                        instance = None
                        try:
                            instance = attr()
                        except Exception:
                            pass
                        if instance is not None:
                            bound = getattr(instance, search_name, None)
                            if callable(bound):
                                return bound, f"{module_name}.{attr_name}.{search_name}", saw_signer

    return None, None, saw_signer


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; upstream repo may be unavailable or setup.sh has not been run."
            )

        search_callable, callable_name, saw_signer = _probe_upstream()
        if search_callable is None:
            if saw_signer:
                raise RuntimeError(
                    "sandbox_infeasible: upstream signer probe succeeded but no search entrypoint was importable"
                )
            raise RuntimeError(
                "sandbox_infeasible: upstream sign/search entrypoints not found"
            )

        response = _call_search(search_callable, query)
        items = _filter_search_items(response)
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
        message = f"{type(exc).__name__}: {exc}"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=_status_from_message(message),
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
