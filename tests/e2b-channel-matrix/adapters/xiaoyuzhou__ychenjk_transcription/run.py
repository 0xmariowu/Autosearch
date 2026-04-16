from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

REPO = "https://github.com/ychenjk-sudo/xiaoyuzhou-transcription-skill"
PLATFORM = "xiaoyuzhou"
PATH_ID = "xiaoyuzhou__ychenjk_transcription"
WORKSPACE_REPO = Path("/tmp/as-matrix/xiaoyuzhou-transcription-skill")
TRANSCRIBE_SCRIPT = WORKSPACE_REPO / "scripts" / "transcribe.sh"
FORMAT_SCRIPT = WORKSPACE_REPO / "scripts" / "format_transcript.py"


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
        if not TRANSCRIBE_SCRIPT.exists() or not FORMAT_SCRIPT.exists():
            raise FileNotFoundError(
                "Expected transcription skill scripts are missing after clone."
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error="sandbox_infeasible: transcription_too_expensive",
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
