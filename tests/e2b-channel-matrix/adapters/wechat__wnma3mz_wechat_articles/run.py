from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/wnma3mz/wechat_articles_spider"
PLATFORM = "wechat"
PATH_ID = "wechat__wnma3mz_wechat_articles"
WORKSPACE_REPO = Path("/tmp/as-matrix/wechat_articles_spider")

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
    module_names = ("wechatarticles", "wechat_articles", "wechat_articles_spider")
    class_names = ("WechatArticle", "WeChatArticle")
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        for class_name in class_names:
            if hasattr(module, class_name):
                return True, f"{module_name}.{class_name}"
    return False, None


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        found_upstream = False
        upstream_symbol: str | None = None
        if WORKSPACE_REPO.exists():
            found_upstream, upstream_symbol = _probe_upstream()

        wx_token = os.environ.get("WECHAT_WX_TOKEN", "").strip()
        cookie = os.environ.get("WECHAT_COOKIE", "").strip()
        if not wx_token or not cookie:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            detail = "missing WECHAT_WX_TOKEN and/or WECHAT_COOKIE"
            if WORKSPACE_REPO.exists() and not found_upstream:
                detail = (
                    "missing WECHAT_WX_TOKEN and/or WECHAT_COOKIE; "
                    "upstream class probe did not resolve"
                )
            elif upstream_symbol:
                detail = (
                    f"missing WECHAT_WX_TOKEN and/or WECHAT_COOKIE; "
                    f"upstream={upstream_symbol}"
                )
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
                "sandbox_infeasible: upstream WechatArticle class not importable"
            )

        raise RuntimeError(
            "needs_login: upstream client requires authenticated wx_token and cookie-backed session"
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
