from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/cv-cat/DouYin_Spider"
PLATFORM = "douyin"
PATH_ID = "douyin__cv_cat_spider"
WORKSPACE_REPO = Path("/tmp/as-matrix/DouYin_Spider")


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
    if any(
        token in lowered
        for token in ("captcha", "verify", "验证码", "anti-bot", "403", "461", "471")
    ):
        return "anti_bot"
    if any(
        token in lowered
        for token in ("login", "cookie", "token", "unauthorized", "401", "s_v_web_id")
    ):
        return "needs_login"
    return "error"


def _load_cookie() -> str | None:
    for env_name in (
        "AS_MATRIX_DOUYIN_CV_CAT_COOKIE",
        "AS_MATRIX_DOUYIN_COOKIE",
        "DOUYIN_COOKIE",
    ):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return None


def _normalize_items(items: object) -> list[object]:
    if not isinstance(items, list):
        return []

    normalized: list[object] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        aweme_info = item.get("aweme_info")
        if isinstance(aweme_info, dict):
            if aweme_info.get("is_ads") or item.get("is_ads"):
                continue
            normalized.append(item)
    return normalized


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    aweme_info = item.get("aweme_info")
    if isinstance(aweme_info, dict):
        for key in ("desc", "title"):
            value = aweme_info.get(key)
            if value:
                return " ".join(str(value).split())[:300]

    for key in ("desc", "title", "content", "text", "snippet", "summary"):
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

    cookie = _load_cookie()
    if not cookie:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="needs_login",
            error=(
                "DouYin_Spider search requires a logged-in Douyin cookie; "
                "set AS_MATRIX_DOUYIN_CV_CAT_COOKIE or DOUYIN_COOKIE."
            ),
        )

    if str(WORKSPACE_REPO) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_REPO))

    try:
        from builder.auth import DouyinAuth
        from dy_apis.douyin_api import DouyinAPI

        auth = DouyinAuth()
        auth.perepare_auth(cookie)
        raw_items, _guide_words = DouyinAPI.search_some_video_work(auth, query, num=20)
        items = _normalize_items(raw_items)
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
        error = f"{type(exc).__name__}: {exc}"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=_status_from_message(error),
            error=error,
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
