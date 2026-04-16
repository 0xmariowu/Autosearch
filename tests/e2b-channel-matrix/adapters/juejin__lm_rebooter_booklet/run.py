from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

REPO = "https://github.com/lm-rebooter/NuggetsBooklet"
PLATFORM = "juejin"
PATH_ID = "juejin__lm_rebooter_booklet"
WORKSPACE_REPO = Path("/tmp/as-matrix/NuggetsBooklet")


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

        top_level = [path.name for path in WORKSPACE_REPO.iterdir()]
        has_library_manifest = any(
            (WORKSPACE_REPO / name).exists()
            for name in ("setup.py", "pyproject.toml", "package.json", "go.mod", "Cargo.toml")
        )
        if has_library_manifest:
            raise RuntimeError(
                "sandbox_infeasible: upstream repo contains project metadata but no importable "
                "keyword-search entrypoint was identified"
            )

        raise RuntimeError(
            "content_archive_no_library: upstream repo is a booklet/content archive "
            f"({len(top_level)} top-level entries) without a callable search client"
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
