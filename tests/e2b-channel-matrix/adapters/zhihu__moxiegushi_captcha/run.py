from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO = "https://github.com/moxiegushi/zhihu"
PLATFORM = "zhihu"
PATH_ID = "zhihu__moxiegushi_captcha"
WORKSPACE_REPO = Path("/tmp/as-matrix/zhihu")
WORKSPACE_FILE = WORKSPACE_REPO / "zhihu.py"

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


def _load_repo_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "as_matrix_moxiegushi_zhihu", WORKSPACE_FILE
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec from {WORKSPACE_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    if not WORKSPACE_REPO.exists():
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error="Repository not found; run setup.sh first",
        )

    try:
        module = _load_repo_module()

        search_callable = getattr(module, "search", None)
        if callable(search_callable):
            try:
                search_callable(query)
            except Exception:
                pass

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="anti_bot",
            error=(
                "moxiegushi/zhihu is a CAPTCHA-driven login crawler; "
                "search requires interactive verification in sandbox."
            ),
            anti_bot_signals=["captcha_login_repo"],
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

    payload = run(args.query, args.query_category)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
