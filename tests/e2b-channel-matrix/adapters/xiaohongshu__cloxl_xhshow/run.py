from __future__ import annotations

import argparse
import json
import time

REPO = "https://github.com/Cloxl/xhshow"
PLATFORM = "xiaohongshu"
PATH_ID = "xiaohongshu__cloxl_xhshow"


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
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return _result_payload(
        query,
        query_category,
        elapsed_ms,
        status="sandbox_infeasible",
        items_returned=0,
        avg_content_len=0,
        sample=None,
        error=(
            "Cloxl/xhshow provides x-s signing function only; rule-3 bans "
            "self-written HTTP. Use xiaohongshu__reajason_xhs (needs cookie) or "
            "seo__xiaohongshu instead."
        ),
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
