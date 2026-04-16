from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path

REPO = "https://github.com/littlepai/Unofficial-Zhihu-API"
PLATFORM = "zhihu"
PATH_ID = "zhihu__littlepai_unofficial"
WORKSPACE_REPO = Path("/tmp/as-matrix/Unofficial-Zhihu-API")

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


def _status_from_message(message: str) -> str:
    lowered = message.lower()
    if "timeout" in lowered:
        return "timeout"
    if any(token in lowered for token in ("captcha", "403", "429", "forbidden")):
        return "anti_bot"
    if any(token in lowered for token in ("login", "cookie", "token", "unauthorized", "401")):
        return "needs_login"
    return "error"


def _clean_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return _clean_text(item)
    if not isinstance(item, dict):
        return _clean_text(item)
    for key in ("title", "text", "content", "summary", "snippet", "name"):
        value = item.get(key)
        if value:
            return _clean_text(value)[:300]
    return _clean_text(json.dumps(item, ensure_ascii=False))[:300]


def _summarize_items(items: list[object]) -> tuple[int, int, str | None]:
    limited_items = list(items[:20])
    if not limited_items:
        return 0, 0, None
    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = texts[0][:200] if texts else None
    return len(limited_items), avg_len, sample or None


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"Repository not found at {WORKSPACE_REPO}; run setup.sh first."
            )

        try:
            from ufzh.zhihu import Search
        except ModuleNotFoundError as exc:
            if exc.name and "tensorflow" in exc.name.lower():
                raise RuntimeError(
                    "sandbox_infeasible: tensorflow_required_for_upstream_search_class"
                ) from exc
            raise

        search_client = Search()
        fetch = search_client.relatedQidByKWord(query)
        items = fetch.fetchone() if hasattr(fetch, "fetchone") else fetch
        if not isinstance(items, list):
            raise TypeError("upstream Search.relatedQidByKWord() did not yield a list")

        items_returned, avg_content_len, sample = _summarize_items(items)
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
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=_status_from_message(message),
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
