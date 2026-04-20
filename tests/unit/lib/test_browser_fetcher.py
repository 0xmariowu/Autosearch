import builtins
import sys
from types import ModuleType
from unittest.mock import AsyncMock, Mock

import pytest

from autosearch.lib.browser_fetcher import (
    DEFAULT_TIMEOUT_MS,
    DEFAULT_USER_AGENT,
    BrowserFetchConfig,
    BrowserNotInstalledError,
    fetch_page_with_js,
)
from autosearch.lib.html_scraper import fetch_page


def _clear_playwright_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "playwright", raising=False)
    monkeypatch.delitem(sys.modules, "playwright.async_api", raising=False)


def _install_fake_playwright(
    monkeypatch: pytest.MonkeyPatch,
    *,
    page_html: str,
    response_status: int = 200,
    launch_side_effect: Exception | None = None,
) -> dict[str, object]:
    _clear_playwright_modules(monkeypatch)

    response = Mock(status=response_status)

    page = Mock()
    page.goto = AsyncMock(return_value=response)
    page.content = AsyncMock(return_value=page_html)
    page.wait_for_selector = AsyncMock()

    context = Mock()
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()

    browser = Mock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    chromium = Mock()
    if launch_side_effect is None:
        chromium.launch = AsyncMock(return_value=browser)
    else:
        chromium.launch = AsyncMock(side_effect=launch_side_effect)

    playwright = Mock(chromium=chromium)
    playwright_context = AsyncMock()
    playwright_context.__aenter__.return_value = playwright
    playwright_context.__aexit__.return_value = False

    async_playwright = Mock(return_value=playwright_context)

    playwright_package = ModuleType("playwright")
    playwright_package.__path__ = []
    async_api_module = ModuleType("playwright.async_api")
    async_api_module.async_playwright = async_playwright

    monkeypatch.setitem(sys.modules, "playwright", playwright_package)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api_module)

    return {
        "async_playwright": async_playwright,
        "browser": browser,
        "chromium": chromium,
        "context": context,
        "page": page,
    }


@pytest.mark.asyncio
async def test_browser_fetcher_raises_when_playwright_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_playwright_modules(monkeypatch)
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "playwright.async_api":
            raise ImportError("No module named 'playwright.async_api'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(BrowserNotInstalledError) as exc_info:
        await fetch_page_with_js("https://example.com/post")

    assert 'pip install "autosearch[browser]"' in str(exc_info.value)
    assert "playwright install chromium" in str(exc_info.value)


@pytest.mark.asyncio
async def test_browser_fetcher_raises_when_chromium_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_playwright(
        monkeypatch,
        page_html="<html></html>",
        launch_side_effect=RuntimeError("Executable doesn't exist"),
    )

    with pytest.raises(BrowserNotInstalledError) as exc_info:
        await fetch_page_with_js("https://example.com/post")

    assert "Chromium binary not found" in str(exc_info.value)
    assert "playwright install chromium" in str(exc_info.value)


def test_browser_fetch_config_defaults() -> None:
    config = BrowserFetchConfig()

    assert config.headless is True
    assert config.timeout_ms == DEFAULT_TIMEOUT_MS
    assert config.user_agent == DEFAULT_USER_AGENT
    assert config.wait_for_selector is None
    assert config.wait_until == "networkidle"
    assert config.extra_http_headers is None


@pytest.mark.asyncio
async def test_fetch_page_with_js_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    mocks = _install_fake_playwright(
        monkeypatch,
        page_html="""
        <html>
          <head><title>Browser Title</title></head>
          <body>
            <article>
              <p>Loaded via JS.</p>
              <a href="/about">About</a>
            </article>
          </body>
        </html>
        """,
        response_status=206,
    )

    page = await fetch_page_with_js("https://example.com/post", run_prune=False)

    assert page.status_code == 206
    assert page.metadata["title"] == "Browser Title"
    assert "# Browser Title" not in page.markdown
    assert "Loaded via JS." in page.markdown
    assert page.links[0].href == "https://example.com/about"
    assert mocks["page"].goto.await_count == 1


@pytest.mark.asyncio
async def test_fetch_page_with_js_wait_for_selector_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocks = _install_fake_playwright(
        monkeypatch,
        page_html="<html><body><article>Ready</article></body></html>",
    )
    config = BrowserFetchConfig(wait_for_selector="article", timeout_ms=12_345)

    await fetch_page_with_js("https://example.com/post", config=config)

    mocks["page"].wait_for_selector.assert_awaited_once_with(
        "article",
        timeout=12_345,
    )


@pytest.mark.asyncio
async def test_fetch_page_with_js_reuses_html_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html>
      <head>
        <title>Shared Parser</title>
        <meta property="og:description" content="Same output" />
      </head>
      <body>
        <article>
          <p>Rendered content.</p>
          <a href="/story">Story</a>
          <img src="/image.png" alt="Hero" />
        </article>
      </body>
    </html>
    """

    async def fake_fetch_html(*args: object, **kwargs: object) -> str:
        return html

    monkeypatch.setattr("autosearch.lib.html_scraper.fetch_html", fake_fetch_html)
    _install_fake_playwright(monkeypatch, page_html=html)

    static_page = await fetch_page("https://example.com/post", run_prune=False)
    browser_page = await fetch_page_with_js("https://example.com/post", run_prune=False)

    assert browser_page.model_dump(exclude={"fetched_at"}) == static_page.model_dump(
        exclude={"fetched_at"}
    )
