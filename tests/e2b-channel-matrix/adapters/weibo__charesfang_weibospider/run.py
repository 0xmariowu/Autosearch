from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

REPO = "https://github.com/CharesFang/WeiboSpider"
PLATFORM = "weibo"
PATH_ID = "weibo__charesfang_weibospider"
WORKSPACE_REPO = Path("/tmp/as-matrix/WeiboSpider")

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

        try:
            importlib.import_module("scrapy")
        except Exception as exc:
            raise RuntimeError("sandbox_infeasible: scrapy_runtime") from exc

        spider_module = importlib.import_module("WeiboSpider.spiders.weibo_spider")
        spider_class = getattr(spider_module, "WeiboSpider", None)
        if spider_class is None:
            raise AttributeError("sandbox_infeasible: WeiboSpider.spiders.weibo_spider.WeiboSpider missing")

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
                "CharesFang/WeiboSpider is a Scrapy uid-based timeline crawler. "
                "It imports successfully, but it does not expose a free-text keyword "
                "search entrypoint for arbitrary Weibo queries."
            ),
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        lower = message.lower()
        status = "error"
        if "scrapy_runtime" in lower:
            status = "error"
        elif any(token in lower for token in ("timeout", "timed out")):
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
