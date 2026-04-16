from __future__ import annotations

import argparse
import json
import time

REPO = "https://github.com/DIYgod/RSSHub"
PATH_ID = "jike__rsshub_public"
PLATFORM = "jike"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    args = parser.parse_args()

    started = time.perf_counter()
    payload = {
        "platform": PLATFORM,
        "path_id": PATH_ID,
        "repo": REPO,
        "query": args.query,
        "query_category": args.query_category,
        "status": "empty",
        "items_returned": 0,
        "avg_content_len": 0,
        "sample": None,
        "error": "RSSHub no keyword endpoint for Jike.",
        "total_ms": int((time.perf_counter() - started) * 1000),
        "anti_bot_signals": [],
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
