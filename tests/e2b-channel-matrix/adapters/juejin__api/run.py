from __future__ import annotations

import argparse
import json
import re
import time

import httpx

REPO = "https://api.juejin.cn/search_api/v1/search"
PLATFORM = "juejin"
PATH_ID = "juejin__api"
SEARCH_URL = "https://api.juejin.cn/search_api/v1/search"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


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


def _clean_text(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return _clean_text(item)
    if not isinstance(item, dict):
        return _clean_text(item)

    for key in (
        "title",
        "summary",
        "brief_content",
        "content",
        "description",
        "snippet",
        "article_title",
        "article_brief_content",
    ):
        value = item.get(key)
        if value:
            return _clean_text(value)

    for key in ("article_info", "article", "content_info"):
        nested = item.get(key)
        if isinstance(nested, dict):
            text = _extract_item_text(nested)
            if text:
                return text

    return _clean_text(json.dumps(item, ensure_ascii=False))


def _has_real_content(item: object) -> bool:
    return bool(_extract_item_text(item).strip())


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


def _collect_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        return [item for item in payload if _has_real_content(item)]
    if not isinstance(payload, dict):
        return []

    items: list[object] = []
    data = payload.get("data")
    if isinstance(data, list):
        items.extend(data)
    elif isinstance(data, dict):
        for key in ("articles", "list", "posts", "items"):
            value = data.get(key)
            if isinstance(value, list):
                items.extend(value)
    for key in ("articles", "list", "posts", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            items.extend(value)

    return [item for item in items if _has_real_content(item)]


def _search_post(client: httpx.Client, query: str) -> list[object]:
    response = client.post(
        SEARCH_URL,
        json={
            "keyword": query,
            "id_type": 0,
            "sort_type": 0,
            "search_type": 0,
            "cursor": "0",
            "limit": 20,
        },
    )
    response.raise_for_status()
    return _collect_items(response.json())


def _search_get(client: httpx.Client, query: str) -> list[object]:
    response = client.get(
        SEARCH_URL,
        params={"query": query, "id_type": 0, "sort_type": 0},
    )
    response.raise_for_status()
    return _collect_items(response.json())


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": "https://juejin.cn/search?query=",
            "Accept": "application/json, text/plain, */*",
        }
        with httpx.Client(
            headers=headers, follow_redirects=True, timeout=10.0, trust_env=False
        ) as client:
            items: list[object]
            try:
                items = _search_post(client, query)
            except Exception:
                items = []

            if not items:
                items = _search_get(client, query)

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
    except httpx.TimeoutException as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="timeout",
            error=f"{type(exc).__name__}: {exc}",
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
