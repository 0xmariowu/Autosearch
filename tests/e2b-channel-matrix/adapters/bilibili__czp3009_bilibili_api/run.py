from __future__ import annotations

import argparse
import importlib
import json
import shutil
import sys
import time
from pathlib import Path

REPO = "https://github.com/czp3009/bilibili-api"
PLATFORM = "bilibili"
PATH_ID = "bilibili__czp3009_bilibili_api"
WORKSPACE_REPO = Path("/tmp/as-matrix/bilibili-api-czp3009")

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
        try:
            importlib.import_module("jpype")
        except ImportError:
            pass

        if shutil.which("java") is None:
            raise RuntimeError("language_mismatch: JVM required")

        raise RuntimeError("language_mismatch: JVM required")
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
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
