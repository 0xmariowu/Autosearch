from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = "https://github.com/chyroc/WechatSogou"
WORKSPACE_REPO = Path("/tmp/as-matrix/WechatSogou")
if str(WORKSPACE_REPO) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_REPO))


def _result_payload(
    query: str, query_category: str, elapsed_ms: int, **extra: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "platform": "wechat",
        "path_id": "wechat__sogou",
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

    article = item.get("article")
    gzh = item.get("gzh")
    if isinstance(article, dict):
        title = str(article.get("title") or "")
        abstract = str(article.get("abstract") or "")
        account_name = ""
        if isinstance(gzh, dict):
            account_name = str(gzh.get("wechat_name") or "")
        text = " ".join(part for part in (title, abstract, account_name) if part)
        if text:
            return text

    for key in ("content", "desc", "summary", "snippet", "title", "text"):
        value = item.get(key)
        if value:
            return str(value)
    return json.dumps(item, ensure_ascii=False)[:300]


def _summarize_items(items: list[object]) -> tuple[int, int, str | None]:
    limited_items = items[:20]
    if not limited_items:
        return 0, 0, None
    texts = [_extract_item_text(item) for item in limited_items]
    avg_len = int(sum(len(text) for text in texts) / len(texts))
    sample = " ".join(texts[0].split())[:200]
    return len(limited_items), avg_len, sample or None


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
        import wechatsogou

        api = wechatsogou.WechatSogouAPI()
        response = api.search_article(query)
        items = response if isinstance(response, list) else []
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
        lower = message.lower()
        anti_bot_signals: list[str] = []
        status = "error"
        if any(token in lower for token in ("captcha", "验证码", "verify code")):
            status = "anti_bot"
            if "captcha" in lower or "验证码" in lower:
                anti_bot_signals.append("captcha")
            if "403" in lower:
                anti_bot_signals.append("403")
        elif "timeout" in lower:
            status = "timeout"
        return _result_payload(
            query,
            query_category,
            elapsed_ms,
            status=status,
            error=message,
            anti_bot_signals=anti_bot_signals,
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
