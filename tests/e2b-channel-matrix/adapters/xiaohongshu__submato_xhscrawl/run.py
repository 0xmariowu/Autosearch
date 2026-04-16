from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import time
from pathlib import Path

REPO = "https://github.com/submato/xhscrawl"
PLATFORM = "xiaohongshu"
PATH_ID = "xiaohongshu__submato_xhscrawl"
WORKSPACE_REPO = Path("/tmp/as-matrix/xhscrawl")
DEMO_MODULE = WORKSPACE_REPO / "demo" / "xhs.py"


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
        for token in ("captcha", "verify", "slide", "验证码", "滑块", "461", "471", "406")
    ):
        return "anti_bot"
    if any(
        token in lowered
        for token in ("login", "cookie", "token", "unauthorized", "401", "403")
    ):
        return "needs_login"
    return "error"


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    note_card = item.get("note_card")
    if isinstance(note_card, dict):
        for key in ("display_title", "title", "desc", "content"):
            value = note_card.get(key)
            if value:
                return " ".join(str(value).split())[:300]

    for key in ("content", "desc", "body", "text", "title", "snippet", "summary"):
        value = item.get(key)
        if value:
            return " ".join(str(value).split())[:300]

    return json.dumps(item, ensure_ascii=False)[:300]


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited_items), avg_len, sample


def _load_cookie() -> str | None:
    for env_name in (
        "AS_MATRIX_XHSCRAWL_COOKIE",
        "AS_MATRIX_XIAOHONGSHU_COOKIE",
        "XIAOHONGSHU_COOKIE",
        "XHS_COOKIE",
    ):
        value = os.environ.get(env_name)
        if value and value.strip():
            return value.strip()
    return None


def _build_search_id() -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    number = (int(time.time() * 1000) << 64) + random.randint(0, 2147483646)
    if number == 0:
        return "0"
    encoded = ""
    while number:
        number, remainder = divmod(number, len(alphabet))
        encoded = alphabet[remainder] + encoded
    return encoded


def _load_demo_module():
    spec = importlib.util.spec_from_file_location("xhscrawl_demo", DEMO_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load demo module from {DEMO_MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_items(response_json: object) -> list[object]:
    if not isinstance(response_json, dict):
        return []
    data = response_json.get("data")
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict) and item.get("model_type") == "note"
    ]


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

    if not DEMO_MODULE.exists():
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error=f"Expected demo signer at {DEMO_MODULE}, but it is missing.",
        )

    cookie = _load_cookie()
    if not cookie:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="needs_login",
            error="xhscrawl search requires a logged-in cookie; set AS_MATRIX_XHSCRAWL_COOKIE or XHS_COOKIE.",
        )

    try:
        module = _load_demo_module()
        response_json = module.sentPostRequest(
            "https://edith.xiaohongshu.com",
            "/api/sns/web/v1/search/notes",
            {
                "keyword": query,
                "page": 1,
                "page_size": 20,
                "search_id": _build_search_id(),
                "sort": "general",
                "note_type": 0,
                "ext_flags": [],
                "geo": "",
                "image_formats": ["jpg", "webp", "avif"],
            },
            cookie,
        )
        items = _extract_items(response_json)
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
    payload = run(**vars(parser.parse_args()))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
