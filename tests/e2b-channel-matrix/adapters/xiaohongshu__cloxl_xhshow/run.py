from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

REPO = "https://github.com/Cloxl/xhshow"
PLATFORM = "xiaohongshu"
PATH_ID = "xiaohongshu__cloxl_xhshow"
WORKSPACE_REPO = Path("/tmp/as-matrix/xhshow")
WORKSPACE_SRC = WORKSPACE_REPO / "src"


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
            "验证码",
            "滑块",
            "anti-bot",
            "antibot",
            "461",
            "471",
            "406",
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


def _parse_cookie_value(raw_cookie: str | None) -> dict[str, str] | str | None:
    if not raw_cookie:
        return None
    raw_cookie = raw_cookie.strip()
    if not raw_cookie:
        return None

    try:
        parsed = json.loads(raw_cookie)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return {str(key): str(value) for key, value in parsed.items()}

    cookie = SimpleCookie()
    cookie.load(raw_cookie)
    if cookie:
        return {key: morsel.value for key, morsel in cookie.items()}

    return raw_cookie


def _load_cookie() -> dict[str, str] | str | None:
    for env_name in (
        "AS_MATRIX_XHSHOW_COOKIE",
        "AS_MATRIX_XIAOHONGSHU_COOKIE",
        "XIAOHONGSHU_COOKIE",
        "XHS_COOKIE",
    ):
        cookie = _parse_cookie_value(os.environ.get(env_name))
        if cookie:
            return cookie
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


def _extract_items(response: Any) -> list[object]:
    if not isinstance(response, dict):
        return []
    data = response.get("data")
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

    cookies = _load_cookie()
    if not cookies:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="needs_login",
            error="xhshow only provides signing helpers; set AS_MATRIX_XHSHOW_COOKIE or XHS_COOKIE with valid Xiaohongshu cookies.",
        )

    if str(WORKSPACE_SRC) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_SRC))
    if str(WORKSPACE_REPO) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_REPO))

    try:
        import requests
        from xhshow import SessionManager, Xhshow

        client = Xhshow()
        session = SessionManager()
        url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
        payload = {
            "keyword": query,
            "page": 1,
            "page_size": 20,
            "search_id": _build_search_id(),
            "sort": "general",
            "note_type": 0,
            "ext_flags": [],
            "geo": "",
            "image_formats": ["jpg", "webp", "avif"],
        }
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.xiaohongshu.com",
            "referer": "https://www.xiaohongshu.com/",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        }
        headers.update(
            client.sign_headers_post(
                uri=url,
                cookies=cookies,
                payload=payload,
                session=session,
            )
        )
        response = requests.post(
            url,
            data=client.build_json_body(payload),
            headers=headers,
            cookies=cookies if isinstance(cookies, dict) else None,
            timeout=10,
        )
        response.raise_for_status()
        response_json = response.json()
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
