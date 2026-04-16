from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/LiuRoy/zhihu_spider"
PLATFORM = "zhihu"
PATH_ID = "zhihu__liuroy_zhihu_spider"
WORKSPACE_REPO = Path("/tmp/as-matrix/zhihu_spider")
PACKAGE_ROOT = WORKSPACE_REPO / "zhihu"

for repo_path in (PACKAGE_ROOT, WORKSPACE_REPO):
    if str(repo_path) not in sys.path:
        sys.path.insert(0, str(repo_path))


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


def _has_login_context() -> bool:
    env_names = (
        "AS_MATRIX_ZHIHU_COOKIE",
        "ZHIHU_COOKIE",
        "AS_MATRIX_ZHIHU_EMAIL",
        "ZHIHU_EMAIL",
        "AS_MATRIX_ZHIHU_PASSWORD",
        "ZHIHU_PASSWORD",
    )
    return any(os.environ.get(name, "").strip() for name in env_names)


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        try:
            importlib.import_module("scrapy")
        except Exception as exc:
            raise RuntimeError("sandbox_infeasible: scrapy_runtime") from exc

        spider_module = importlib.import_module("zhihu.spiders.profile")
        spider_class = getattr(spider_module, "ZhihuSipder", None)
        if spider_class is None:
            raise AttributeError("sandbox_infeasible: zhihu.spiders.profile.ZhihuSipder missing")

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
                    "needs_login: LiuRoy/zhihu_spider is a login-first Scrapy people crawler "
                    "with embedded signin flow and no anonymous free-text search entrypoint."
                ),
            )

        raise RuntimeError(
            "sandbox_infeasible: upstream repo crawls Zhihu people/follow graphs after login rather than exposing keyword search"
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        lower = message.lower()
        status = "error"
        if "needs_login" in lower or any(
            token in lower for token in ("login", "cookie", "password", "signin")
        ):
            status = "needs_login"
        elif any(token in lower for token in ("403", "captcha", "forbidden", "access denied")):
            status = "anti_bot"
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
