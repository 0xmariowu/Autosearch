from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = "https://github.com/ttttmr/Wechat2RSS"
WORKSPACE_REPO = Path("/tmp/as-matrix/Wechat2RSS")
if str(WORKSPACE_REPO) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_REPO))


def _result_payload(
    query: str, query_category: str, elapsed_ms: int, **extra: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "platform": "wechat",
        "path_id": "wechat__wechat2rss",
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
    if not WORKSPACE_REPO.exists():
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error="Repository not found; run setup.sh first",
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return _result_payload(
        query,
        query_category,
        elapsed_ms,
        status="error",
        items_returned=0,
        avg_content_len=0,
        sample=None,
        error="Shell-based upstream repo is not wired into this Python adapter yet",
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
