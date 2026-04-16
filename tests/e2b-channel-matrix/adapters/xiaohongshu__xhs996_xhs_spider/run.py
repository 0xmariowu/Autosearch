from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

REPO = "https://github.com/xhs996/xhs_spider"
PLATFORM = "xiaohongshu"
PATH_ID = "xiaohongshu__xhs996_xhs_spider"
WORKSPACE_REPO = Path("/tmp/as-matrix/xhs_spider")
DEMO_MODULE = WORKSPACE_REPO / "demo.py"


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
        if not DEMO_MODULE.exists():
            raise FileNotFoundError(
                f"Expected upstream entrypoint at {DEMO_MODULE}, but it is missing."
            )

        raise RuntimeError(
            "sandbox_infeasible: upstream repo exposes only a placeholder demo and paid-contact README, with no importable search wrapper for sandbox use"
        )
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
    payload = run(**vars(parser.parse_args()))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
