# Self-written for task F202
from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

from autosearch.core.models import SubQuery

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test News</title>
    <item>
      <title>AI regulation passes EU</title>
      <link>https://news.google.com/rss/articles/abc</link>
      <pubDate>Mon, 15 Apr 2024 10:00:00 GMT</pubDate>
      <description>&lt;a href="https://example.com/story"&gt;AI regulation passes EU&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color="#6f6f6f"&gt;Reuters&lt;/font&gt;</description>
      <source url="https://reuters.com">Reuters</source>
    </item>
    <item>
      <title>Chip exports tighten &amp; markets react</title>
      <link>https://news.google.com/rss/articles/def</link>
      <pubDate>Tue, 16 Apr 2024 08:30:00 GMT</pubDate>
      <description>&lt;a href="https://example.com/story-2"&gt;Chip exports tighten&lt;/a&gt; &lt;b&gt;Markets react&lt;/b&gt;</description>
      <source url="https://nytimes.com">The New York Times</source>
    </item>
    <item>
      <title>Brief without publisher</title>
      <link>https://news.google.com/rss/articles/ghi</link>
      <pubDate>Wed, 17 Apr 2024 09:15:00 GMT</pubDate>
      <description>&lt;a href="https://example.com/story-3"&gt;Brief without publisher&lt;/a&gt;</description>
    </item>
  </channel>
</rss>
"""


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "autosearch"
        / "skills"
        / "channels"
        / "google_news"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_google_news_api_search", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module spec from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()
search = MODULE.search


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _query() -> SubQuery:
    return SubQuery(text="AI regulation", rationale="Need recent news coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_rss_items_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "AI regulation"
        assert request.url.params["hl"] == "en-US"
        assert request.url.params["gl"] == "US"
        assert request.url.params["ceid"] == "US:en"
        return httpx.Response(200, text=RSS_FIXTURE, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 3

    first = results[0]
    assert first.url == "https://news.google.com/rss/articles/abc"
    assert first.title == "AI regulation passes EU"
    assert first.snippet == "AI regulation passes EU Reuters"
    assert first.content == "AI regulation passes EU Reuters"
    assert first.source_channel == "google_news:reuters"

    second = results[1]
    assert second.url == "https://news.google.com/rss/articles/def"
    assert second.title == "Chip exports tighten & markets react"
    assert second.snippet == "Chip exports tighten Markets react"
    assert second.source_channel == "google_news:the-new-york-times"


@pytest.mark.asyncio
async def test_search_strips_html_from_summary() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Example</title>
      <link>https://news.google.com/rss/articles/html</link>
      <description>&lt;a href="x"&gt;Story&lt;/a&gt;&amp;nbsp;&lt;font color="#6f6f6f"&gt;Publisher&lt;/font&gt;</description>
      <source url="https://example.com">Publisher</source>
    </item>
  </channel>
</rss>
"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].snippet == "Story Publisher"


@pytest.mark.asyncio
async def test_search_skips_item_without_link() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Missing link</title>
      <description>&lt;a href="x"&gt;Story&lt;/a&gt;</description>
      <source url="https://example.com">Publisher</source>
    </item>
  </channel>
</rss>
"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []


@pytest.mark.asyncio
async def test_search_handles_missing_source_tag() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>No source</title>
      <link>https://news.google.com/rss/articles/no-source</link>
      <description>&lt;a href="x"&gt;Story&lt;/a&gt;</description>
    </item>
  </channel>
</rss>
"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].source_channel == "google_news"


@pytest.mark.asyncio
async def test_search_publisher_is_sanitized_to_slug() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Slug test</title>
      <link>https://news.google.com/rss/articles/slug</link>
      <description>&lt;a href="x"&gt;Story&lt;/a&gt;</description>
      <source url="https://nytimes.com">The New York Times</source>
    </item>
  </channel>
</rss>
"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert len(results) == 1
    assert results[0].source_channel == "google_news:the-new-york-times"


@pytest.mark.asyncio
async def test_search_returns_empty_on_bozo_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<rss><channel><item></rss>", request=request)

    async with _client(handler) as http_client:
        results = await search(_query(), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "google_news_search_failed"
    assert str(logger.events[0][1]["reason"]) != ""


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Bug 1 (fix-plan): typed exception now propagates instead of [].
    from autosearch.channels.base import (
        ChannelAuthError,
        PermanentError,
        RateLimited,
        TransientError,
    )

    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway", request=request)

    async with _client(handler) as http_client:
        with pytest.raises((TransientError, PermanentError, RateLimited, ChannelAuthError)):
            await search(_query(), http_client=http_client)
    assert logger.events
    assert logger.events[0][0] == "google_news_search_failed"
    assert "502" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_sends_user_agent() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        captured["accept"] = request.headers.get("accept", "")
        return httpx.Response(200, text=RSS_FIXTURE, request=request)

    async with _client(handler) as http_client:
        await search(_query(), http_client=http_client)

    assert captured["user_agent"].startswith("autosearch/")
    assert captured["accept"] == "application/rss+xml, application/xml, text/xml"
