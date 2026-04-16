from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = "https://github.com/ShilongLee/Crawler"
PLATFORM = "kuaishou"
PATH_ID = "kuaishou__shilonglee_crawler"
WORKSPACE_REPO = Path("/tmp/as-matrix/Crawler")


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
        for token in ("login", "cookie", "token", "unauthorized", "401", "no_account")
    ):
        return "needs_login"
    return "error"


def _load_cookie() -> str | None:
    for env_name in (
        "AS_MATRIX_KUAISHOU_SHILONGLEE_COOKIE",
        "AS_MATRIX_KUAISHOU_COOKIE",
        "KUAISHOU_COOKIE",
    ):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return None


@contextmanager
def _repo_root() -> object:
    original_cwd = Path.cwd()
    try:
        os.chdir(WORKSPACE_REPO)
        yield
    finally:
        os.chdir(original_cwd)


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    photo = item.get("photo")
    if isinstance(photo, dict):
        for key in ("caption", "title", "text", "content", "description", "snippet"):
            value = photo.get(key)
            if value:
                return " ".join(str(value).split())[:300]

    for key in ("caption", "title", "text", "content", "description", "snippet"):
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


async def _run(query: str, query_category: str, cookie: str) -> dict[str, object]:
    started = time.perf_counter()

    try:
        if str(WORKSPACE_REPO) not in sys.path:
            sys.path.insert(0, str(WORKSPACE_REPO))

        with _repo_root():
            from service.kuaishou.logic import request_search

            response, success = await request_search(query, cookie, offset=0, limit=20)

        if not success:
            raise RuntimeError(f"upstream_search_failed: {response}")

        items = response if isinstance(response, list) else []
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
            status=_status_from_message(error),
            error=error,
        )


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

    cookie = _load_cookie()
    if not cookie:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="needs_login",
            error=(
                "ShilongLee/Crawler kuaishou search requires a logged-in Kuaishou cookie; "
                "set AS_MATRIX_KUAISHOU_SHILONGLEE_COOKIE or KUAISHOU_COOKIE."
            ),
        )

    return asyncio.run(_run(query, query_category, cookie))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    payload = run(**vars(parser.parse_args()))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
