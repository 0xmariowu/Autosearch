from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

REPO = "https://github.com/ldh2068vip/36krCrawler"
PLATFORM = "36kr"
PATH_ID = "36kr__ldh2068vip_crawler"
WORKSPACE_REPO = Path("/tmp/as-matrix/36krCrawler")


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

        java_files = list(WORKSPACE_REPO.rglob("*.java"))
        if java_files or (WORKSPACE_REPO / "pom.xml").exists() or (WORKSPACE_REPO / "src").exists():
            raise RuntimeError("language_mismatch: jvm_required")

        raise RuntimeError("sandbox_infeasible: no Python entrypoint found")
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        if shutil.which("java") is None and WORKSPACE_REPO.exists():
            message = "RuntimeError: language_mismatch: jvm_required"
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
    print(json.dumps(run(**vars(parser.parse_args())), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
