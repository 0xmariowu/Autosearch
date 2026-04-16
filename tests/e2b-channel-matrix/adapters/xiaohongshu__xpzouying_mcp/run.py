from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

REPO = "https://github.com/xpzouying/xiaohongshu-mcp"
PLATFORM = "xiaohongshu"
PATH_ID = "xiaohongshu__xpzouying_mcp"
WORKSPACE_REPO = Path("/tmp/as-matrix/xiaohongshu-mcp")
WORKSPACE_BINARY = WORKSPACE_REPO / "xiaohongshu-mcp"


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

        go_available = shutil.which("go") is not None
        binary_available = WORKSPACE_BINARY.exists()

        if not go_available and not binary_available:
            raise RuntimeError("go_runtime_required")

        if not (
            os.environ.get("AS_MATRIX_XIAOHONGSHU_MCP_COOKIE")
            or os.environ.get("AS_MATRIX_XIAOHONGSHU_COOKIE")
            or os.environ.get("XIAOHONGSHU_COOKIE")
            or os.environ.get("XHS_COOKIE")
        ):
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="needs_login",
                error="xiaohongshu-mcp requires browser-backed login cookies before search tools are usable.",
            )

        raise RuntimeError(
            "sandbox_infeasible: upstream MCP server requires a browser-backed Go runtime workflow that is not reproducible from this Python adapter without external login/bootstrap"
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        status = "error"
        if "login" in message.lower() or "cookie" in message.lower():
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
    payload = run(**vars(parser.parse_args()))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
