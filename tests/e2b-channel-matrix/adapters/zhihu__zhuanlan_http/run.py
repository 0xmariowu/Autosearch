from __future__ import annotations

import argparse
import html
import json
import re
import time

import httpx

REPO = "https://www.zhihu.com/api/v4/search_v3"
PLATFORM = "zhihu"
PATH_ID = "zhihu__zhuanlan_http"
SEARCH_URL = "https://www.zhihu.com/api/v4/search_v3"
CONTENT_TYPES = {"answer", "article", "zvideo"}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
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
    text = "" if value is None else str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())


def _extract_item_text(item: object) -> str:
    if isinstance(item, str):
        return _clean_text(item)
    if not isinstance(item, dict):
        return _clean_text(item)

    question = item.get("question")
    if isinstance(question, dict):
        for key in ("name", "title"):
            value = question.get(key)
            if value:
                return _clean_text(value)

    author = item.get("author")
    if isinstance(author, dict):
        author_name = author.get("name")
    else:
        author_name = None

    for key in (
        "title",
        "excerpt",
        "description",
        "snippet",
        "content",
        "name",
        "headline",
        "text",
    ):
        value = item.get(key)
        if value:
            text = _clean_text(value)
            if author_name and text:
                return f"{author_name} {text}"[:300]
            return text[:300]

    return _clean_text(json.dumps(item, ensure_ascii=False))[:300]


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


def _anti_bot_signals(response: httpx.Response, body_text: str) -> list[str]:
    lowered = body_text.lower()
    signals: list[str] = []

    if response.status_code == 403:
        signals.append("http_403")
    if response.status_code == 429:
        signals.append("http_429")
    if "signin" in str(response.url).lower() or "login" in str(response.url).lower():
        signals.append("signin_redirect")
    if any(
        token in lowered
        for token in (
            "sign in to zhihu",
            "登录知乎",
            "登录后",
            "captcha",
            "安全验证",
            "验证你不是机器人",
            "访问受限",
            "unhuman",
        )
    ):
        signals.append("anti_bot_page")
    if "text/html" in response.headers.get("content-type", "").lower():
        if "<html" in lowered:
            signals.append("html_response")

    deduped: list[str] = []
    for signal in signals:
        if signal not in deduped:
            deduped.append(signal)
    return deduped


def _extract_items(payload: object) -> list[object]:
    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if not isinstance(data, list):
        return []

    items: list[object] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        obj = entry.get("object")
        if not isinstance(obj, dict):
            continue
        if obj.get("type") in CONTENT_TYPES:
            items.append(obj)
    return items


def run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": "https://www.zhihu.com/search?type=content&q=",
            "Accept": "application/json, text/plain, */*",
        }
        response = httpx.get(
            SEARCH_URL,
            params={
                "t": "general",
                "q": query,
                "correction": "1",
                "offset": "0",
                "limit": "20",
            },
            headers=headers,
            timeout=10.0,
            follow_redirects=True,
            trust_env=False,
        )

        body_text = response.text[:4000]
        signals = _anti_bot_signals(response, body_text)
        if any(
            signal in signals
            for signal in ("http_403", "http_429", "signin_redirect", "anti_bot_page")
        ):
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return _result_payload(
                query,
                query_category,
                elapsed_ms,
                status="anti_bot",
                error="Zhihu anti-bot or sign-in wall detected",
                anti_bot_signals=signals,
            )

        response.raise_for_status()
        payload = response.json()
        items = _extract_items(payload)
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
    except json.JSONDecodeError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status="anti_bot",
            error=f"{type(exc).__name__}: {exc}",
            anti_bot_signals=["non_json_response"],
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
