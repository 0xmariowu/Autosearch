"""Optional Playwright-backed browser fetcher for JS-rendered pages.
Install with: `pip install "autosearch[browser]" && playwright install chromium`.
Usage: `from autosearch.lib.browser_fetcher import fetch_page_with_js`.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from autosearch.core.models import FetchedPage

LOGGER = structlog.get_logger(__name__).bind(component="browser_fetcher")
DEFAULT_TIMEOUT_MS = 30_000
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class BrowserNotInstalledError(RuntimeError):
    """Raised when Playwright or Chromium is not available."""


@dataclass(frozen=True)
class BrowserFetchConfig:
    headless: bool = True
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    user_agent: str = DEFAULT_USER_AGENT
    wait_for_selector: str | None = None
    wait_until: str = "networkidle"
    extra_http_headers: dict[str, str] | None = None


async def fetch_page_with_js(
    url: str,
    *,
    config: BrowserFetchConfig | None = None,
    run_prune: bool = True,
) -> FetchedPage:
    """Navigate to a URL with Chromium, then return the shared FetchedPage shape."""
    cfg = config or BrowserFetchConfig()

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise BrowserNotInstalledError(
            "Playwright is not installed. To use browser fetch: "
            'pip install "autosearch[browser]" && playwright install chromium'
        ) from exc

    LOGGER.debug(
        "browser_fetch_start",
        url=url,
        headless=cfg.headless,
        wait_until=cfg.wait_until,
        wait_for_selector=cfg.wait_for_selector,
    )

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=cfg.headless)
        except Exception as exc:
            raise BrowserNotInstalledError(
                "Chromium binary not found. Run: playwright install chromium"
            ) from exc

        context = None
        try:
            context = await browser.new_context(
                user_agent=cfg.user_agent,
                extra_http_headers=cfg.extra_http_headers or {},
            )
            page = await context.new_page()
            response = await page.goto(
                url,
                timeout=cfg.timeout_ms,
                wait_until=cfg.wait_until,
            )
            if cfg.wait_for_selector:
                await page.wait_for_selector(
                    cfg.wait_for_selector,
                    timeout=cfg.timeout_ms,
                )
            html = await page.content()
            status_code = response.status if response is not None else 0
        finally:
            try:
                if context is not None:
                    await context.close()
            finally:
                await browser.close()

    LOGGER.debug("browser_fetch_complete", url=url, status_code=status_code)

    # Import locally so the optional Playwright feature stays decoupled from the static path.
    from autosearch.lib.html_scraper import _parse_html_into_page

    return _parse_html_into_page(
        url=url,
        html=html,
        status_code=status_code,
        run_prune=run_prune,
    )
