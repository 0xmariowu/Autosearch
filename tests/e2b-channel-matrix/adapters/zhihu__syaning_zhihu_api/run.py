from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

REPO = "https://github.com/syaning/zhihu-api"
PLATFORM = "zhihu"
PATH_ID = "zhihu__syaning_zhihu_api"
WORKSPACE_REPO = Path("/tmp/as-matrix/zhihu-api-syaning")


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


def _load_cookie() -> str | None:
    for env_name in (
        "AS_MATRIX_ZHIHU_COOKIE",
        "ZHIHU_COOKIE",
        "AS_MATRIX_SYANING_ZHIHU_COOKIE",
    ):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return None


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        node_bin = shutil.which("node")
        if node_bin is None:
            raise RuntimeError("language_mismatch: node_required")

        probe = subprocess.run(
            [
                node_bin,
                "-e",
                (
                    "const api=require(process.argv[1])();"
                    "console.log(JSON.stringify(Object.keys(api).sort()));"
                ),
                str(WORKSPACE_REPO),
            ],
            cwd=WORKSPACE_REPO,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if probe.returncode != 0:
            stderr = (probe.stderr or probe.stdout or "").strip()
            raise RuntimeError(stderr or f"node probe failed with exit code {probe.returncode}")

        keys = json.loads((probe.stdout.strip().splitlines() or ["[]"])[-1])
        if "search" in keys:
            raise RuntimeError(
                "sandbox_infeasible: search key exists unexpectedly; adapter needs a repo-specific node invocation update"
            )

        cookie = _load_cookie()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if not cookie:
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="needs_login",
                items_returned=0,
                avg_content_len=0,
                sample=None,
                error=(
                    "needs_login: syaning/zhihu-api is a Node SDK whose README requires "
                    "cookie() before requests, and its exported surface is user/topic/"
                    "question/answer/column oriented rather than free-text search."
                ),
            )

        raise RuntimeError(
            "sandbox_infeasible: upstream JS SDK does not expose a keyword-search API"
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="timeout",
            error=f"TimeoutExpired: {exc}",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        lower = message.lower()
        status = "error"
        if "needs_login" in lower or "cookie" in lower:
            status = "needs_login"
        elif "timeout" in lower:
            status = "timeout"
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
    args = parser.parse_args()

    print(json.dumps(run(args.query, args.query_category), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
