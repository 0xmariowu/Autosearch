from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

REPO = "https://github.com/Rockyzsu/xueqiu"
PLATFORM = "xueqiu"
PATH_ID = "xueqiu__rockyzsu_xueqiu"
WORKSPACE_REPO = Path("/tmp/as-matrix/rockyzsu-xueqiu")


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

        main_script = WORKSPACE_REPO / "snowball.py"
        if not main_script.exists():
            raise RuntimeError("sandbox_infeasible: upstream snowball.py entrypoint is missing")

        source = main_script.read_text(encoding="utf-8", errors="ignore")
        if "/snowman/login" in source and "/favs?page=" in source:
            raise RuntimeError(
                "sandbox_infeasible: upstream script is a Python 2 login crawler for "
                "favorite articles and does not expose keyword search"
            )

        raise RuntimeError(
            "sandbox_infeasible: no keyword-search entrypoint found in upstream Python repo"
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
    args = parser.parse_args()

    print(json.dumps(run(args.query, args.query_category), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
