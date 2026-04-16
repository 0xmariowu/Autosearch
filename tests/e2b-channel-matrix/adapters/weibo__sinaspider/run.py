from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

REPO = "https://github.com/LiuXingMing/SinaSpider"
PLATFORM = "weibo"
PATH_ID = "weibo__sinaspider"
WORKSPACE_REPO = Path("/tmp/as-matrix/SinaSpider")
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

    reason = "requires redis + scrapy distributed stack, not bootable in sandbox"
    detail: str | None = None

    try:
        if not WORKSPACE_REPO.exists():
            raise ModuleNotFoundError(f"repository not found at {WORKSPACE_REPO}")
        importlib.import_module("scrapy")
        importlib.import_module("redis")
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    error = reason if detail is None else f"{reason}; {detail}"
    return _result_payload(
        query,
        query_category,
        elapsed_ms,
        status="error",
        error=error,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--query-category", required=True)
    args = parser.parse_args()

    payload = run(args.query, args.query_category)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
