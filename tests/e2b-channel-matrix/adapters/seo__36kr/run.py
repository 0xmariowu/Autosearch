from __future__ import annotations

import argparse
import json
import time

REPO = "https://github.com/deedy5/ddgs"
SITE = "36kr.com"
PATH_ID = "seo__36kr"
PLATFORM = "36kr"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--query-category", required=True)
    args = ap.parse_args()
    started = time.perf_counter()
    try:
        from ddgs import DDGS

        search_query = f"{args.query} site:{SITE}"
        results = list(DDGS().text(search_query, max_results=10, backend="bing"))
        texts = [(r.get("body") or r.get("title") or "") for r in results]
        avg_len = int(sum(len(t) for t in texts) / len(texts)) if texts else 0
        sample = texts[0][:200] if texts else None
        elapsed = int((time.perf_counter() - started) * 1000)
        print(
            json.dumps(
                {
                    "platform": PLATFORM,
                    "path_id": PATH_ID,
                    "repo": REPO,
                    "query": args.query,
                    "query_category": args.query_category,
                    "status": "ok" if results else "empty",
                    "items_returned": len(results),
                    "avg_content_len": avg_len,
                    "total_ms": elapsed,
                    "sample": sample,
                    "anti_bot_signals": [],
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        print(
            json.dumps(
                {
                    "platform": PLATFORM,
                    "path_id": PATH_ID,
                    "repo": REPO,
                    "query": args.query,
                    "query_category": args.query_category,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "total_ms": elapsed,
                    "anti_bot_signals": [],
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
