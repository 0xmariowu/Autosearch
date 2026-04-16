from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

REPO = "https://github.com/yuncaiji/API"
PLATFORM = "kuaishou"
PATH_ID = "kuaishou__yuncaiji_api"
WORKSPACE_REPO = Path("/tmp/as-matrix/API")


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


def _python_files(repo_path: Path) -> list[Path]:
    return [
        path
        for path in repo_path.rglob("*.py")
        if ".git" not in path.parts and "__pycache__" not in path.parts
    ]


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    if not WORKSPACE_REPO.exists():
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error=f"Repository not found at {WORKSPACE_REPO}; run setup.sh first.",
        )

    py_files = _python_files(WORKSPACE_REPO)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if not py_files:
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error=(
                "Upstream repo does not ship a local Python module for Kuaishou. "
                "The clone is effectively README-only and documents a paid remote API/token flow."
            ),
        )

    return _result_payload(
        query,
        query_category,
        elapsed_ms,
        status="error",
        error="No usable upstream Kuaishou endpoint module discovered in clone.",
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
