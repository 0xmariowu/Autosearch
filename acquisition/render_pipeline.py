"""Render fallback for acquisition.

Uses a local Playwright browser when available. This keeps the render path
inside our own runtime boundary and avoids relying on external services.
"""

from __future__ import annotations

from typing import Any

from .document_models import AcquiredDocument


def _playwright_sync():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - import availability is environment-specific
        raise RuntimeError("playwright render fallback not available") from exc
    return sync_playwright


def _render_with_playwright(url: str, *, timeout: int = 15) -> dict[str, Any]:
    sync_playwright = _playwright_sync()
    timeout_ms = max(int(timeout), 1) * 1000
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(str(url or "").strip(), wait_until="networkidle", timeout=timeout_ms)
            html = page.content()
            title = page.title()
            final_url = page.url
        finally:
            browser.close()
    return {
        "url": str(url or "").strip(),
        "final_url": str(final_url or url or "").strip(),
        "title": str(title or "").strip(),
        "raw_html": str(html or ""),
    }


def render_document(
    url: str,
    *,
    timeout: int = 15,
) -> AcquiredDocument:
    rendered = _render_with_playwright(url, timeout=timeout)
    document = AcquiredDocument.from_html(
        rendered["url"],
        rendered["raw_html"],
        content_type="text/html",
        final_url=rendered.get("final_url"),
        status_code=200,
        fetch_method="render_fallback",
        metadata={"pipeline": "render_fallback"},
        used_render_fallback=True,
    )
    if rendered.get("title") and not document.title:
        document.title = str(rendered.get("title") or "")
    return document
