from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = "https://github.com/erma0/douyin"
PLATFORM = "douyin"
PATH_ID = "douyin__erma0"
WORKSPACE_REPO = Path("/tmp/as-matrix/douyin")


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
        for token in ("login", "cookie", "sessionid", "ttwid", "__ac_nonce", "401")
    ):
        return "needs_login"
    return "error"


def _load_cookie() -> str | None:
    for env_name in (
        "AS_MATRIX_DOUYIN_ERMA0_COOKIE",
        "AS_MATRIX_DOUYIN_COOKIE",
        "DOUYIN_COOKIE",
    ):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return None


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)

    for key in (
        "desc",
        "title",
        "author_nickname",
        "author_signature",
        "content",
        "text",
        "snippet",
        "summary",
    ):
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
                "erma0/douyin requires a logged-in Douyin cookie for search; "
                "set AS_MATRIX_DOUYIN_ERMA0_COOKIE or DOUYIN_COOKIE."
            ),
        )

    child_code = """
import json
import sys

repo_path, query, cookie = sys.argv[1:4]
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

from backend.lib.douyin.crawler import Douyin

items = []

def on_new_items(new_items, _type):
    items.extend(new_items or [])

douyin = Douyin(
    target=query,
    limit=20,
    type="search",
    down_path="/tmp/as-matrix/erma0-search-output",
    cookie=cookie,
    filters={"sort_type": "0", "publish_time": "0", "filter_duration": ""},
    on_new_items=on_new_items,
)
douyin.run()
print(json.dumps(items[:20], ensure_ascii=False))
"""

    try:
        completed = subprocess.run(
            [sys.executable, "-c", child_code, str(WORKSPACE_REPO), query, cookie],
            cwd=WORKSPACE_REPO,
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(
                stderr or f"subprocess exited with {completed.returncode}"
            )

        stdout = completed.stdout.strip().splitlines()
        payload_line = stdout[-1] if stdout else "[]"
        items = json.loads(payload_line)
        if not isinstance(items, list):
            raise TypeError("upstream subprocess did not return a JSON list")

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
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="timeout",
            error=f"TimeoutExpired: {exc}",
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
