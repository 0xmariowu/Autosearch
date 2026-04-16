from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

REPO = "https://github.com/dataabc/weibo-crawler"
PLATFORM = "weibo"
PATH_ID = "weibo__dataabc_weibo_crawler"
WORKSPACE_REPO = Path("/tmp/as-matrix/weibo-crawler")

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


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        module = importlib.import_module("weibo")
        weibo_class = getattr(module, "Weibo", None)
        if weibo_class is None:
            raise AttributeError("sandbox_infeasible: upstream Weibo class not found")

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="empty",
            items_returned=0,
            avg_content_len=0,
            sample=None,
            note=(
                "dataabc/weibo-crawler is importable, but its public entrypoint crawls "
                "user timelines by user_id/config rather than exposing a free-text "
                "keyword-search API for arbitrary queries."
            ),
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        lower = message.lower()
        status = "error"
        if any(token in lower for token in ("timeout", "timed out")):
            status = "timeout"
        elif any(token in lower for token in ("403", "forbidden", "captcha", "access denied")):
            status = "anti_bot"
        elif any(token in lower for token in ("login", "cookie", "token", "unauthorized")):
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
    args = parser.parse_args()

    print(json.dumps(run(args.query, args.query_category), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
