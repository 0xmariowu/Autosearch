from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

REPO = "https://github.com/Nemo2011/bilibili-api"
WORKSPACE_REPO = Path("/tmp/as-matrix/bilibili-api")
if str(WORKSPACE_REPO) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_REPO))


def _result_payload(
    query: str, query_category: str, elapsed_ms: int, **extra: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "platform": "bilibili",
        "path_id": "bilibili__nemo2011",
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
        return item
    if not isinstance(item, dict):
        return str(item)

    for key in (
        "content",
        "snippet",
        "body",
        "description",
        "summary",
        "title",
        "text",
    ):
        value = item.get(key)
        if value:
            return str(value)

    return json.dumps(item, ensure_ascii=False)


def _summarize_items(
    items: list[object], max_items: int = 20
) -> tuple[int, int, str | None]:
    limited_items = list(items[:max_items])
    if not limited_items:
        return 0, 0, None

    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = " ".join(texts[0].split())[:200]
    return len(limited_items), avg_len, sample or None


async def _run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    try:
        from bilibili_api import search

        response = await search.search(keyword=query)
        # Bilibili search returns result groups keyed by result_type.
        # Only keep content types useful for research: video, article, bili_user.
        # Exclude: tips, live_user, live_room, upuser empty sets, etc.
        CONTENT_TYPES = {"video", "article", "bili_user", "media_bangumi", "media_ft"}
        items: list[object] = []
        if isinstance(response, dict):
            groups = response.get("result") or response.get("items") or []
            if (
                isinstance(groups, list)
                and groups
                and isinstance(groups[0], dict)
                and "result_type" in groups[0]
            ):
                for group in groups:
                    if group.get("result_type") in CONTENT_TYPES:
                        data = group.get("data") or []
                        if isinstance(data, list):
                            items.extend(data)
            else:
                items = groups if isinstance(groups, list) else []
        elif isinstance(response, list):
            items = response

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

    payload = asyncio.run(_run(args.query, args.query_category))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
