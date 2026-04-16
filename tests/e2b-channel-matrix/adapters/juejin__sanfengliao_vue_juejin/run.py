from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

REPO = "https://github.com/sanfengliao/vue-juejin"
PLATFORM = "juejin"
PATH_ID = "juejin__sanfengliao_vue_juejin"
WORKSPACE_REPO = Path("/tmp/as-matrix/vue-juejin")


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

        if not (WORKSPACE_REPO / "package.json").exists():
            raise RuntimeError("ui_project_no_library: missing package.json")

        if not (WORKSPACE_REPO / "src").exists():
            raise RuntimeError("ui_project_no_library: missing src/")

        raise RuntimeError(
            "ui_project_no_library: upstream repo is a Vue client UI and does not expose "
            "a reusable Python/CLI keyword-search library"
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
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
