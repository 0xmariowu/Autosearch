from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/liqiongyu/xueqiu_mcp"
PATH_ID = "xueqiu__mcp"
PLATFORM = "xueqiu"
WORKSPACE_REPO = Path("/tmp/as-matrix/xueqiu_mcp")

if str(WORKSPACE_REPO) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_REPO))


def _payload(
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
        "name",
        "code",
        "symbol",
        "title",
        "description",
        "market",
        "type",
    ):
        value = item.get(key)
        if value:
            return str(value)

    return json.dumps(item, ensure_ascii=False)


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = " ".join(texts[0].split())[:200]
    return len(limited_items), avg_len, sample or None


def _extract_items(data: object) -> list[object]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("stocks", "list", "data", "items", "quotes", "result"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested

    for value in data.values():
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested

    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    args = parser.parse_args()

    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"xueqiu_mcp repo is missing at {WORKSPACE_REPO}; run setup.sh first."
            )

        token = os.environ.get("XUEQIU_TOKEN", "").strip()
        if not token:
            payload = _payload(
                args.query,
                args.query_category,
                int((time.perf_counter() - started) * 1000),
                status="needs_login",
                error="XUEQIU_TOKEN is required by xueqiu_mcp / pysnowball.",
            )
            print(json.dumps(payload, ensure_ascii=False))
            return 0

        xueqiu_main = importlib.import_module("main")
        search_fn = getattr(xueqiu_main, "suggest_stock")
        response = search_fn(args.query)
        items = _extract_items(response)
        items_returned, avg_content_len, sample = _summarize_items(items)
        payload = _payload(
            args.query,
            args.query_category,
            int((time.perf_counter() - started) * 1000),
            status="ok" if items_returned else "empty",
            items_returned=items_returned,
            avg_content_len=avg_content_len,
            sample=sample,
        )
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        lowered = message.lower()
        status = "error"
        if any(token in lowered for token in ("token", "login", "cookie", "401", "unauthorized")):
            status = "needs_login"
        payload = _payload(
            args.query,
            args.query_category,
            int((time.perf_counter() - started) * 1000),
            status=status,
            error=message,
        )

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
