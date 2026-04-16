from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/cv-cat/Spider_XHS"
PLATFORM = "xiaohongshu"
PATH_ID = "xiaohongshu__cv_cat_spider_xhs"
WORKSPACE_REPO = Path("/tmp/as-matrix/Spider_XHS")
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
        for token in (
            "captcha",
            "verify",
            "slide",
            "验证码",
            "滑块",
            "461",
            "471",
            "406",
            "blocked",
        )
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
        "AS_MATRIX_SPIDER_XHS_COOKIE",
        "AS_MATRIX_XIAOHONGSHU_COOKIE",
        "XIAOHONGSHU_COOKIE",
        "XHS_COOKIE",
    ):
        value = os.environ.get(env_name)
        if value and value.strip():
            return value.strip()
    return None


def _extract_items(items: object) -> list[object]:
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

    cookies = _load_cookie()
    if not cookies:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="needs_login",
            error="Spider_XHS search requires a logged-in cookie; set AS_MATRIX_SPIDER_XHS_COOKIE or XHS_COOKIE.",
        )

    try:
        from apis.xhs_pc_apis import XHS_Apis

        client = XHS_Apis()
        success, msg, items = client.search_some_note(
            query,
            20,
            cookies,
            sort_type_choice=0,
            note_type=0,
        )
        if not success:
            raise RuntimeError(str(msg))

        filtered_items = _extract_items(items)
        items_returned, avg_content_len, sample = _summarize_items(
            filtered_items, max_items=20
        )
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
