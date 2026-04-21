from __future__ import annotations

import asyncio
import importlib
import time
from types import ModuleType
from typing import Any

import structlog

LOGGER = structlog.get_logger(__name__).bind(component="tool", skill="fetch-crawl4ai")

DEFAULT_TIMEOUT_SECONDS = 30.0
CRAWL4AI_UNAVAILABLE_SUGGEST = (
    "pip install crawl4ai + playwright install chromium, or fall back to fetch-jina"
)
ANTI_BOT_SUGGEST = "try fetch-playwright or fetch-firecrawl paid fallback"
ANTI_BOT_STATUS_CODES = {401, 403, 418, 429, 451}
ANTI_BOT_MARKERS = (
    "access denied",
    "anti-bot",
    "blocked by anti-bot",
    "captcha",
    "cloudflare",
    "forbidden",
    "perimeterx",
    "please verify",
    "robot",
    "security check",
    "security verification",
    "verify you are human",
    "访问验证",
    "安全验证",
)
NETWORK_ERROR_MARKERS = (
    "connection refused",
    "connection reset",
    "dns",
    "err_aborted",
    "err_connection",
    "err_name_not_resolved",
    "net::",
    "network",
    "socket",
)

FetchCrawl4AIResult = dict[str, object]


def fetch(
    url: str,
    *,
    wait_for: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    crawl4ai_module: ModuleType | None = None,
) -> FetchCrawl4AIResult:
    """Fetch a URL as Markdown through crawl4ai's Playwright-backed crawler."""
    crawl4ai = crawl4ai_module if crawl4ai_module is not None else _load_crawl4ai()
    if crawl4ai is None:
        return _failure(
            source=url,
            reason="crawl4ai_unavailable",
            suggest=CRAWL4AI_UNAVAILABLE_SUGGEST,
        )

    started = time.perf_counter()
    try:
        result = asyncio.run(
            asyncio.wait_for(
                _crawl_once(
                    url,
                    wait_for=wait_for,
                    timeout_seconds=timeout_seconds,
                    crawl4ai=crawl4ai,
                ),
                timeout=max(timeout_seconds, 0.001),
            )
        )
    except Exception as exc:  # crawl4ai intentionally stays optional at import time.
        elapsed_sec = time.perf_counter() - started
        reason = _classify_exception(exc)
        LOGGER.warning("fetch_crawl4ai_failed", url=url, reason=reason, error=str(exc))
        return _failure(
            source=url,
            reason=reason,
            message=str(exc) or exc.__class__.__name__,
            stderr_tail=_stderr_tail(getattr(exc, "stderr", None)),
            meta=_failure_meta(elapsed_sec=elapsed_sec),
        )

    elapsed_sec = time.perf_counter() - started
    status_code = _to_int(getattr(result, "status_code", None))
    markdown = _extract_markdown(result)
    html = str(getattr(result, "html", "") or "")
    error_message = str(getattr(result, "error_message", "") or "")
    final_url = str(getattr(result, "redirected_url", None) or getattr(result, "url", None) or url)
    metadata = getattr(result, "metadata", None)
    title = _extract_title(markdown=markdown, metadata=metadata)

    if _looks_like_anti_bot(
        status_code=status_code,
        markdown=markdown,
        html=html,
        error_message=error_message,
    ):
        return _failure(
            source=url,
            reason="anti_bot_blocked",
            message=error_message or f"crawl4ai reported blocked HTTP {status_code}",
            status_code=status_code,
            suggest=ANTI_BOT_SUGGEST,
            meta=_failure_meta(elapsed_sec=elapsed_sec, status_code=status_code),
        )

    if not bool(getattr(result, "success", False)):
        return _failure(
            source=url,
            reason="crawl4ai_runtime_error",
            message=error_message or "crawl4ai returned an unsuccessful result",
            status_code=status_code,
            meta=_failure_meta(elapsed_sec=elapsed_sec, status_code=status_code),
        )

    if len(markdown.strip()) < 10:
        return _failure(
            source=url,
            reason="empty_content",
            message="crawl4ai returned empty or too-short markdown",
            status_code=status_code,
            meta=_failure_meta(elapsed_sec=elapsed_sec, status_code=status_code),
        )

    return {
        "ok": True,
        "markdown": markdown,
        "title": title,
        "url": final_url,
        "meta": {
            "status_code": status_code,
            "backend": "crawl4ai",
            "browser": "chromium",
            "elapsed_sec": elapsed_sec,
        },
        "source": url,
    }


def _load_crawl4ai() -> ModuleType | None:
    try:
        return importlib.import_module("crawl4ai")
    except ImportError:
        return None


async def _crawl_once(
    url: str,
    *,
    wait_for: str | None,
    timeout_seconds: float,
    crawl4ai: ModuleType,
) -> Any:
    browser_config = crawl4ai.BrowserConfig(headless=True)
    run_config = crawl4ai.CrawlerRunConfig(
        cache_mode=crawl4ai.CacheMode.BYPASS,
        wait_for=wait_for,
        page_timeout=max(1, int(timeout_seconds * 1000)),
    )

    async with crawl4ai.AsyncWebCrawler(config=browser_config) as crawler:
        return await crawler.arun(url=url, config=run_config)


def _failure(*, source: str, reason: str, **extra: object) -> FetchCrawl4AIResult:
    result: FetchCrawl4AIResult = {"ok": False, "reason": reason, "source": source}
    result.update({key: value for key, value in extra.items() if value is not None})
    return result


def _failure_meta(*, elapsed_sec: float, status_code: int | None = None) -> dict[str, object]:
    return {
        "status_code": status_code,
        "backend": "crawl4ai",
        "browser": "chromium",
        "elapsed_sec": elapsed_sec,
    }


def _extract_markdown(result: object) -> str:
    markdown = getattr(result, "markdown", "")
    if markdown is None:
        return ""

    raw_markdown = getattr(markdown, "raw_markdown", None)
    if raw_markdown is not None:
        return str(raw_markdown)

    if isinstance(markdown, dict):
        return str(markdown.get("raw_markdown") or markdown.get("markdown") or "")

    return str(markdown)


def _extract_title(*, markdown: str, metadata: object) -> str:
    if isinstance(metadata, dict):
        for key in ("title", "og:title", "twitter:title"):
            value = metadata.get(key)
            if value:
                return str(value).strip()

    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("title:"):
            return stripped.split(":", maxsplit=1)[1].strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def _looks_like_anti_bot(
    *,
    status_code: int | None,
    markdown: str,
    html: str,
    error_message: str,
) -> bool:
    if status_code in ANTI_BOT_STATUS_CODES:
        return True

    haystack = f"{error_message}\n{markdown}\n{html}".lower()
    return any(marker in haystack for marker in ANTI_BOT_MARKERS)


def _classify_exception(exc: Exception) -> str:
    if isinstance(exc, TimeoutError | asyncio.TimeoutError):
        return "timeout"

    exc_name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if "timeout" in exc_name or "timeout" in message or "timed out" in message:
        return "timeout"
    if _looks_like_network_error(exc_name=exc_name, message=message):
        return "network_error"
    return "crawl4ai_runtime_error"


def _looks_like_network_error(*, exc_name: str, message: str) -> bool:
    if any(marker in exc_name for marker in ("connection", "network", "socket")):
        return True
    return any(marker in message for marker in NETWORK_ERROR_MARKERS)


def _stderr_tail(stderr: object, *, max_chars: int = 1000) -> str:
    if stderr is None:
        return ""
    if isinstance(stderr, bytes):
        text = stderr.decode(errors="replace")
    else:
        text = str(stderr)
    return text[-max_chars:]


def _to_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
