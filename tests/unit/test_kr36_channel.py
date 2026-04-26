from pathlib import Path

import httpx
import pytest

from autosearch.channels.base import ChannelRegistry, Environment
from autosearch.core.channel_status import exception_to_channel_status
from autosearch.core.models import FetchedPage, SubQuery
from autosearch.lib.html_scraper import HtmlFetchError

SEARCH_RESULTS_HTML = """
<section class="article-item">
  <a class="article-item-title" href="/p/123456789">Example <em>KR36</em> Title</a>
  <div class="article-item-description">Short <em>description</em> for the preview result.</div>
  <span class="article-author">Insight Author</span>
</section>
"""
LEGACY_HTML_ENV = "AUTOSEARCH_KR36_USE_LEGACY"


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _channels_root() -> Path:
    return Path(__file__).resolve().parents[2] / "autosearch" / "skills" / "channels"


def _compiled_kr36():
    registry = ChannelRegistry.compile_from_skills(_channels_root(), Environment())
    return registry.metadata("kr36").methods[0].callable


def _enable_legacy_html(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LEGACY_HTML_ENV, "1")


def _fetched_page(url: str, *, markdown: str) -> FetchedPage:
    return FetchedPage(
        url=url,
        status_code=200,
        html="<html></html>",
        cleaned_html="<article></article>",
        markdown=markdown,
    )


@pytest.mark.asyncio
async def test_kr36_404_returns_transient_error_with_fix_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_callable = _compiled_kr36()
    _enable_legacy_html(monkeypatch)

    async def fake_fetch_html(
        url: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        params: dict[str, str] | None = None,
    ) -> str:
        _ = http_client
        _ = params
        raise HtmlFetchError(url, status_code=404, reason="http_error")

    monkeypatch.setitem(search_callable.__globals__, "fetch_html", fake_fetch_html)

    with pytest.raises(Exception) as raised:
        await search_callable(
            SubQuery(text="ai financing", rationale="Need KR36 coverage"),
        )

    failure = exception_to_channel_status(raised.value)
    fix_hint = failure.fix_hint or ""

    assert failure.status == "transient_error"
    assert fix_hint
    assert "36kr search endpoint" in fix_hint.lower()
    assert "upstream" in fix_hint.lower()


@pytest.mark.asyncio
async def test_kr36_evidence_uses_markdown_from_fetched_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_callable = _compiled_kr36()
    _enable_legacy_html(monkeypatch)
    http_client = httpx.AsyncClient()
    captured: dict[str, object] = {}
    markdown = "# KR36 Article\n\nLong body content."

    async def fake_fetch_html(
        url: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        params: dict[str, str] | None = None,
    ) -> str:
        captured["search_url"] = url
        captured["search_client"] = http_client
        captured["params"] = params
        return SEARCH_RESULTS_HTML

    async def fake_fetch_page(
        url: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> FetchedPage:
        captured["page_url"] = url
        captured["page_client"] = client
        return _fetched_page(url, markdown=markdown)

    monkeypatch.setitem(search_callable.__globals__, "fetch_html", fake_fetch_html)
    monkeypatch.setitem(search_callable.__globals__, "fetch_page", fake_fetch_page)

    try:
        results = await search_callable(
            SubQuery(text="ai financing", rationale="Need KR36 coverage"),
            http_client=http_client,
        )
    finally:
        await http_client.aclose()

    assert len(results) == 1
    evidence = results[0]
    assert evidence.content == markdown
    assert evidence.snippet == markdown[:300]
    assert evidence.source_page is not None
    assert evidence.source_page.markdown == markdown
    assert captured["page_url"] == "https://www.36kr.com/p/123456789"
    assert captured["page_client"] is http_client


@pytest.mark.asyncio
async def test_kr36_falls_back_on_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    search_callable = _compiled_kr36()
    _enable_legacy_html(monkeypatch)

    async def fake_fetch_html(
        url: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        params: dict[str, str] | None = None,
    ) -> str:
        _ = url
        _ = http_client
        _ = params
        return SEARCH_RESULTS_HTML

    async def fake_fetch_page(
        url: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> FetchedPage:
        _ = client
        raise HtmlFetchError(url, reason="timeout")

    monkeypatch.setitem(search_callable.__globals__, "fetch_html", fake_fetch_html)
    monkeypatch.setitem(search_callable.__globals__, "fetch_page", fake_fetch_page)
    monkeypatch.setitem(search_callable.__globals__, "LOGGER", logger)

    results = await search_callable(
        SubQuery(text="ai financing", rationale="Need KR36 coverage"),
    )

    assert len(results) == 1
    evidence = results[0]
    assert evidence.snippet == "Short description for the preview result."
    assert evidence.content == "Short description for the preview result."
    assert evidence.source_page is None
    assert logger.events
    assert logger.events[0][0] == "kr36_result_fetch_failed"
    assert logger.events[0][1]["url"] == "https://www.36kr.com/p/123456789"


@pytest.mark.asyncio
async def test_kr36_preserves_title_and_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_callable = _compiled_kr36()
    _enable_legacy_html(monkeypatch)

    async def fake_fetch_html(
        url: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        params: dict[str, str] | None = None,
    ) -> str:
        _ = url
        _ = http_client
        _ = params
        return SEARCH_RESULTS_HTML

    async def fake_fetch_page(
        url: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> FetchedPage:
        _ = client
        return _fetched_page(url, markdown="# KR36 Article\n\nLong body content.")

    monkeypatch.setitem(search_callable.__globals__, "fetch_html", fake_fetch_html)
    monkeypatch.setitem(search_callable.__globals__, "fetch_page", fake_fetch_page)

    results = await search_callable(
        SubQuery(text="ai financing", rationale="Need KR36 coverage"),
    )

    assert len(results) == 1
    evidence = results[0]
    assert evidence.title == "Example KR36 Title"
    assert evidence.url == "https://www.36kr.com/p/123456789"
    assert evidence.source_channel == "kr36:insight-author"
