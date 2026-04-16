from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/donlon/xyz-fetcher"
PLATFORM = "xiaoyuzhou"
PATH_ID = "xiaoyuzhou__donlon_xyz_fetcher"
WORKSPACE_REPO = Path("/tmp/as-matrix/xyz-fetcher")
MODULE_PATH = WORKSPACE_REPO / "src" / "main.py"

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


def _load_upstream_module() -> object:
    spec = importlib.util.spec_from_file_location("xyz_fetcher_main", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load upstream module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _has_login_context() -> bool:
    env_names = (
        "AS_MATRIX_JIKE_ACCESS_TOKEN",
        "JIKE_ACCESS_TOKEN",
        "AS_MATRIX_JIKE_REFRESH_TOKEN",
        "JIKE_REFRESH_TOKEN",
        "AS_MATRIX_XYZ_FETCHER_TOKEN_FILE",
        "XYZ_FETCHER_TOKEN_FILE",
    )
    return any(os.environ.get(name, "").strip() for name in env_names)


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )
        if not MODULE_PATH.exists():
            raise FileNotFoundError(
                f"Expected upstream entrypoint at {MODULE_PATH}, but it is missing."
            )

        _load_upstream_module()

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if not _has_login_context():
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="needs_login",
                items_returned=0,
                avg_content_len=0,
                sample=None,
                error=(
                    "needs_login: donlon/xyz-fetcher reads token/config files and "
                    "fetches podcasts or episodes by ID, not anonymous keyword search."
                ),
            )

        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="empty",
            items_returned=0,
            avg_content_len=0,
            sample=None,
            note="scope_mismatch: id_fetch_only",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        lower = message.lower()
        status = "error"
        if any(token in lower for token in ("login", "token", "cookie", "unauthorized")):
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
