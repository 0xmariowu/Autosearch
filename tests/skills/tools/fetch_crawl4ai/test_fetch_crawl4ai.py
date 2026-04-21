from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load_fetch_crawl4ai() -> ModuleType:
    root = Path(__file__).resolve().parents[4]
    fetch_path = root / "autosearch" / "skills" / "tools" / "fetch-crawl4ai" / "fetch.py"
    spec = importlib.util.spec_from_file_location("fetch_crawl4ai_under_test", fetch_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FETCH_CRAWL4AI = _load_fetch_crawl4ai()


class FakeBrowserConfig:
    def __init__(self, *, headless: bool) -> None:
        self.headless = headless


class FakeCrawlerRunConfig:
    def __init__(
        self,
        *,
        cache_mode: object,
        wait_for: str | None,
        page_timeout: int,
    ) -> None:
        self.cache_mode = cache_mode
        self.wait_for = wait_for
        self.page_timeout = page_timeout


def _crawl4ai_module(
    result: object | None = None,
    *,
    arun_error: Exception | None = None,
    captured: dict[str, object] | None = None,
) -> SimpleNamespace:
    captured = captured if captured is not None else {}
    cache_mode = SimpleNamespace(BYPASS="bypass")

    class FakeAsyncWebCrawler:
        def __init__(self, *, config: FakeBrowserConfig) -> None:
            captured["browser_config"] = config

        async def __aenter__(self) -> "FakeAsyncWebCrawler":
            captured["entered"] = True
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            captured["exited"] = True

        async def arun(self, *, url: str, config: FakeCrawlerRunConfig) -> object:
            captured["url"] = url
            captured["run_config"] = config
            if arun_error is not None:
                raise arun_error
            return result

    return SimpleNamespace(
        AsyncWebCrawler=FakeAsyncWebCrawler,
        BrowserConfig=FakeBrowserConfig,
        CrawlerRunConfig=FakeCrawlerRunConfig,
        CacheMode=cache_mode,
    )


def test_url_happy_path_returns_markdown() -> None:
    result = SimpleNamespace(
        success=True,
        markdown=SimpleNamespace(raw_markdown="# Rendered Title\n\nHello from the browser."),
        url="https://example.test/input",
        redirected_url="https://example.test/final",
        status_code=200,
        metadata={"title": "Rendered Title"},
    )

    response = FETCH_CRAWL4AI.fetch(
        "https://example.test/input",
        crawl4ai_module=_crawl4ai_module(result),
    )

    assert response["ok"] is True
    assert response["markdown"] == "# Rendered Title\n\nHello from the browser."
    assert response["title"] == "Rendered Title"
    assert response["url"] == "https://example.test/final"
    assert response["meta"]["status_code"] == 200
    assert response["meta"]["backend"] == "crawl4ai"
    assert response["meta"]["browser"] == "chromium"
    assert isinstance(response["meta"]["elapsed_sec"], float)
    assert response["source"] == "https://example.test/input"


def test_crawl4ai_unavailable_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(FETCH_CRAWL4AI, "_load_crawl4ai", lambda: None)

    response = FETCH_CRAWL4AI.fetch("https://example.test")

    assert response == {
        "ok": False,
        "reason": "crawl4ai_unavailable",
        "source": "https://example.test",
        "suggest": "pip install crawl4ai + playwright install chromium, or fall back to fetch-jina",
    }


def test_runtime_error_returns_structured_error() -> None:
    response = FETCH_CRAWL4AI.fetch(
        "https://example.test",
        crawl4ai_module=_crawl4ai_module(arun_error=RuntimeError("browser crashed")),
    )

    assert response["ok"] is False
    assert response["reason"] == "crawl4ai_runtime_error"
    assert response["source"] == "https://example.test"
    assert response["message"] == "browser crashed"
    assert response["meta"]["backend"] == "crawl4ai"


def test_empty_markdown_returns_empty_content_error() -> None:
    result = SimpleNamespace(
        success=True,
        markdown=SimpleNamespace(raw_markdown="short"),
        url="https://example.test",
        status_code=200,
        metadata={},
    )

    response = FETCH_CRAWL4AI.fetch(
        "https://example.test",
        crawl4ai_module=_crawl4ai_module(result),
    )

    assert response["ok"] is False
    assert response["reason"] == "empty_content"
    assert response["source"] == "https://example.test"
    assert response["status_code"] == 200


def test_wait_for_selector_is_passed_to_crawler_config() -> None:
    captured: dict[str, object] = {}
    result = SimpleNamespace(
        success=True,
        markdown="Title: Dashboard\n\nLoaded dynamic content.",
        url="https://example.test/dashboard",
        status_code=200,
        metadata={},
    )
    crawl4ai = _crawl4ai_module(result, captured=captured)

    response = FETCH_CRAWL4AI.fetch(
        "https://example.test/dashboard",
        wait_for=".dashboard-ready",
        timeout_seconds=12.5,
        crawl4ai_module=crawl4ai,
    )

    assert response["ok"] is True
    assert captured["url"] == "https://example.test/dashboard"
    assert isinstance(captured["browser_config"], FakeBrowserConfig)
    assert captured["browser_config"].headless is True
    assert isinstance(captured["run_config"], FakeCrawlerRunConfig)
    assert captured["run_config"].cache_mode == crawl4ai.CacheMode.BYPASS
    assert captured["run_config"].wait_for == ".dashboard-ready"
    assert captured["run_config"].page_timeout == 12500


def test_anti_bot_blocked_returns_degradation_hint() -> None:
    result = SimpleNamespace(
        success=False,
        markdown="Access denied",
        html="<html><body>Verify you are human</body></html>",
        url="https://blocked.example",
        status_code=403,
        error_message="Blocked by anti-bot protection",
        metadata={},
    )

    response = FETCH_CRAWL4AI.fetch(
        "https://blocked.example",
        crawl4ai_module=_crawl4ai_module(result),
    )

    assert response["ok"] is False
    assert response["reason"] == "anti_bot_blocked"
    assert response["suggest"] == "try fetch-playwright or fetch-firecrawl paid fallback"
    assert response["status_code"] == 403
