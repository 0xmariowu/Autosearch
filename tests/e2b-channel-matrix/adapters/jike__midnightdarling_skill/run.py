from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/MidnightDarling/jike-skill"
PLATFORM = "jike"
PATH_ID = "jike__midnightdarling_skill"
WORKSPACE_REPO = Path("/tmp/as-matrix/jike-skill")
PACKAGE_ROOT = WORKSPACE_REPO / "src"

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


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return " ".join(item.split())
    if not isinstance(item, dict):
        return " ".join(str(item).split())

    for key in (
        "content",
        "body",
        "text",
        "title",
        "snippet",
        "summary",
    ):
        value = item.get(key)
        if value:
            return " ".join(str(value).split())

    return " ".join(json.dumps(item, ensure_ascii=False).split())[:300]


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited_items), avg_len, sample or None


def _load_tokens() -> tuple[str | None, str | None]:
    access_token = None
    refresh_token = None
    for env_name in ("AS_MATRIX_JIKE_ACCESS_TOKEN", "JIKE_ACCESS_TOKEN"):
        value = os.environ.get(env_name, "").strip()
        if value:
            access_token = value
            break
    for env_name in ("AS_MATRIX_JIKE_REFRESH_TOKEN", "JIKE_REFRESH_TOKEN"):
        value = os.environ.get(env_name, "").strip()
        if value:
            refresh_token = value
            break
    return access_token, refresh_token


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        from jike import JikeClient, TokenPair

        access_token, refresh_token = _load_tokens()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if not access_token or not refresh_token:
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="needs_login",
                items_returned=0,
                avg_content_len=0,
                sample=None,
                error=(
                    "needs_login: MidnightDarling/jike-skill uses QR-code auth and "
                    "requires JIKE_ACCESS_TOKEN plus JIKE_REFRESH_TOKEN for search."
                ),
            )

        client = JikeClient(TokenPair(access_token=access_token, refresh_token=refresh_token))
        response = client.search(keyword=query)

        if isinstance(response, dict):
            items = response.get("data") or response.get("items") or response.get("list") or []
        elif isinstance(response, list):
            items = response
        else:
            items = []

        items_returned, avg_content_len, sample = _summarize_items(items, max_items=20)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="ok" if items_returned else "empty",
            items_returned=items_returned,
            avg_content_len=avg_content_len,
            sample=sample,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        message = f"{type(exc).__name__}: {exc}"
        lower = message.lower()
        status = "error"
        if any(token in lower for token in ("login", "token", "qr", "auth")):
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
