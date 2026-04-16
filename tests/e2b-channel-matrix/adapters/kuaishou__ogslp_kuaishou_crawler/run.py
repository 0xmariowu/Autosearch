from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/oGsLP/kuaishou-crawler"
PLATFORM = "kuaishou"
PATH_ID = "kuaishou__ogslp_kuaishou_crawler"
WORKSPACE_REPO = Path("/tmp/as-matrix/kuaishou-crawler")


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


def _load_upstream_module(module_path: Path) -> object:
    spec = importlib.util.spec_from_file_location("as_matrix_ogslp_kuaishou", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _has_login_material() -> bool:
    env_names = (
        "AS_MATRIX_KUAISHOU_OGSLP_COOKIE",
        "AS_MATRIX_KUAISHOU_OGSLP_DID",
        "KUAISHOU_COOKIE",
        "KUAISHOU_DID",
    )
    return any(os.environ.get(name, "").strip() for name in env_names)


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

    module_path = WORKSPACE_REPO / "lib" / "crawler.py"
    if not module_path.exists():
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error="Upstream crawler module lib/crawler.py is missing from clone.",
        )

    try:
        if str(WORKSPACE_REPO) not in sys.path:
            sys.path.insert(0, str(WORKSPACE_REPO))
        module = _load_upstream_module(module_path)
        getattr(module, "Crawler")
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if not _has_login_material():
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="needs_login",
            error=(
                "oGsLP/kuaishou-crawler requires logged-in Kuaishou cookie/didweb material, "
                "and the repo only documents user-feed crawling rather than keyword search."
            ),
        )

    return _result_payload(
        query,
        query_category,
        elapsed_ms,
        status="error",
        error=(
            "Upstream repo exposes user-id feed crawling/download workflows only; "
            "no keyword-search entrypoint was found for the channel-matrix adapter."
        ),
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
