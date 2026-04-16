from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

REPO = "https://github.com/NanmiCoder/MediaCrawler"
PATH_ID = "kuaishou__mediacrawler"
PLATFORM = "kuaishou"
WORKSPACE_REPO = Path("/tmp/as-matrix/MediaCrawler")

if str(WORKSPACE_REPO) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_REPO))


def _payload(
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
        return item
    if not isinstance(item, dict):
        return str(item)

    photo = item.get("photo") if isinstance(item.get("photo"), dict) else {}
    for key in ("caption", "title", "text", "content", "description", "snippet"):
        value = item.get(key)
        if value:
            return str(value)
        photo_value = photo.get(key)
        if photo_value:
            return str(photo_value)

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


def _classify_exception(exc: Exception) -> tuple[str, str]:
    message = f"{type(exc).__name__}: {exc}"
    lowered = message.lower()
    if "playwright" in lowered and (
        "executable doesn't exist" in lowered
        or "please run the following command" in lowered
        or "browser" in lowered
    ):
        return (
            "needs_login",
            f"{message}. MediaCrawler requires Playwright browsers in e2b.",
        )
    if any(token in lowered for token in ("cookie", "login", "qrcode", "unauthorized", "401")):
        return (
            "needs_login",
            f"{message}. MediaCrawler Kuaishou search requires valid cookies/login state.",
        )
    return "error", message


async def _run(query: str, query_category: str) -> dict[str, object]:
    started = time.perf_counter()

    try:
        if not WORKSPACE_REPO.exists():
            raise FileNotFoundError(
                f"MediaCrawler repo is missing at {WORKSPACE_REPO}; run setup.sh first."
            )

        import media_platform.kuaishou  # noqa: F401
        import config as mc_config
        import store.kuaishou as kuaishou_store
        from media_platform.kuaishou.core import KuaishouCrawler

        cookie = os.environ.get("MEDIACRAWLER_KUAISHOU_COOKIE", "").strip()
        if not cookie:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return _payload(
                query,
                query_category,
                elapsed_ms,
                status="needs_login",
                error=(
                    "MediaCrawler Kuaishou search requires a cookie. "
                    "Set MEDIACRAWLER_KUAISHOU_COOKIE in the e2b sandbox."
                ),
            )

        collected_items: list[object] = []

        async def _capture_video(video_item: object) -> None:
            collected_items.append(video_item)

        mc_config.PLATFORM = "ks"
        mc_config.KEYWORDS = query
        mc_config.CRAWLER_TYPE = "search"
        mc_config.LOGIN_TYPE = "cookie"
        mc_config.COOKIES = cookie
        mc_config.HEADLESS = True
        mc_config.SAVE_LOGIN_STATE = False
        mc_config.ENABLE_CDP_MODE = False
        mc_config.CDP_CONNECT_EXISTING = False
        mc_config.ENABLE_GET_COMMENTS = False
        mc_config.CRAWLER_MAX_NOTES_COUNT = 20
        mc_config.START_PAGE = 1
        mc_config.CRAWLER_MAX_SLEEP_SEC = 0

        original_update = kuaishou_store.update_kuaishou_video
        kuaishou_store.update_kuaishou_video = _capture_video
        crawler = KuaishouCrawler()
        try:
            await crawler.start()
        finally:
            kuaishou_store.update_kuaishou_video = original_update
            close = getattr(crawler, "close", None)
            browser_context = getattr(crawler, "browser_context", None)
            if callable(close) and browser_context is not None:
                await close()

        items_returned, avg_content_len, sample = _summarize_items(collected_items)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return _payload(
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
        status, error = _classify_exception(exc)
        return _payload(
            query,
            query_category,
            elapsed_ms,
            status=status,
            error=error,
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
