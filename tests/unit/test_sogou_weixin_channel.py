from pathlib import Path

import httpx
import pytest

from autosearch.channels.base import ChannelRegistry, Environment
from autosearch.core.models import FetchedPage, SubQuery
from autosearch.lib.html_scraper import HtmlFetchError

SEARCH_RESULTS_HTML = """
<ul>
  <li id="sogou_vr_11002601_box_0">
    <div class="txt-box">
      <h3><a href="https://mp.weixin.qq.com/s/example">Example <em>Article</em> Title</a></h3>
      <p class="txt-info">Short <em>search</em> snippet for the preview result.</p>
      <a class="account">AI Weekly</a>
    </div>
  </li>
</ul>
"""


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _channels_root() -> Path:
    return Path(__file__).resolve().parents[2] / "autosearch" / "skills" / "channels"


def _compiled_sogou_weixin():
    registry = ChannelRegistry.compile_from_skills(_channels_root(), Environment())
    return registry.metadata("sogou_weixin").methods[0].callable


def _fetched_page(url: str, *, markdown: str) -> FetchedPage:
    return FetchedPage(
        url=url,
        status_code=200,
        html="<html></html>",
        cleaned_html="<article></article>",
        markdown=markdown,
    )


@pytest.mark.asyncio
async def test_sogou_weixin_evidence_uses_markdown_from_fetched_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_callable = _compiled_sogou_weixin()
    http_client = httpx.AsyncClient()
    captured: dict[str, object] = {}
    markdown = "# Article Title\n\nLong body content."

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
            SubQuery(text="ai agents", rationale="Need Weixin coverage"),
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
    assert captured["page_url"] == "https://mp.weixin.qq.com/s/example"
    assert captured["page_client"] is http_client


@pytest.mark.asyncio
async def test_sogou_weixin_falls_back_on_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    search_callable = _compiled_sogou_weixin()

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
        SubQuery(text="ai agents", rationale="Need Weixin coverage"),
    )

    assert len(results) == 1
    evidence = results[0]
    assert evidence.snippet == "Short search snippet for the preview result."
    assert evidence.content == "Short search snippet for the preview result."
    assert evidence.source_page is None
    assert logger.events
    assert logger.events[0][0] == "sogou_weixin_result_fetch_failed"
    assert logger.events[0][1]["url"] == "https://mp.weixin.qq.com/s/example"


@pytest.mark.asyncio
async def test_sogou_weixin_preserves_title_and_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_callable = _compiled_sogou_weixin()

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
        return _fetched_page(url, markdown="# Article Title\n\nLong body content.")

    monkeypatch.setitem(search_callable.__globals__, "fetch_html", fake_fetch_html)
    monkeypatch.setitem(search_callable.__globals__, "fetch_page", fake_fetch_page)

    results = await search_callable(
        SubQuery(text="ai agents", rationale="Need Weixin coverage"),
    )

    assert len(results) == 1
    evidence = results[0]
    assert evidence.title == "Example Article Title"
    assert evidence.url == "https://mp.weixin.qq.com/s/example"
    assert evidence.source_channel == "sogou_weixin:ai-weekly"
