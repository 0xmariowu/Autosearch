from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/bowenpay/wechat-spider"
PLATFORM = "wechat"
PATH_ID = "wechat__bowenpay_wechat_spider"
WORKSPACE_REPO = Path("/tmp/as-matrix/wechat-spider")

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


def _probe_upstream() -> tuple[bool, str | None]:
    candidates = (
        ("wechatspider", "wechatspider"),
        ("spider", "spider"),
        ("main", "main"),
        ("manage", "manage"),
    )
    for module_name, entry_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        if hasattr(module, entry_name) or hasattr(module, "main"):
            return True, module_name
    return False, None


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        found_upstream = False
        upstream_module: str | None = None
        if WORKSPACE_REPO.exists():
            found_upstream, upstream_module = _probe_upstream()

        cookie = os.environ.get("WECHAT_COOKIE", "").strip()
        if not cookie:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            detail = "missing WECHAT_COOKIE"
            if WORKSPACE_REPO.exists() and not found_upstream:
                detail = "missing WECHAT_COOKIE; upstream entry probe did not resolve"
            elif upstream_module:
                detail = f"missing WECHAT_COOKIE; upstream={upstream_module}"
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="needs_login",
                items_returned=0,
                avg_content_len=0,
                sample=None,
                error=f"needs_login: {detail}",
            )

        if not found_upstream:
            raise RuntimeError(
                "sandbox_infeasible: upstream spider/main entrypoint not importable"
            )

        raise RuntimeError(
            "needs_login: upstream scraper requires authenticated cookie plus external services"
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        status = "needs_login" if "needs_login" in message.lower() else "error"
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
