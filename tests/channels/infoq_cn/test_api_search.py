# Self-written for task F204
from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest

from autosearch.core.models import SubQuery

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>InfoQ CN</title>
    <item>
      <title>LLM 大模型落地实践</title>
      <link>https://www.infoq.cn/article/llm-practice</link>
      <description>&lt;p&gt;企业如何把 LLM 能力接入平台。&lt;/p&gt;</description>
      <pubDate>Tue, 15 Apr 2024 10:00:00 GMT</pubDate>
      <category>AI</category>
      <category>大模型</category>
    </item>
    <item>
      <title>AI Agent 工程化</title>
      <link>https://www.infoq.cn/article/ai-agent</link>
      <description>&lt;p&gt;从提示工程到 LLM 系统设计。&lt;/p&gt;</description>
      <pubDate>Tue, 16 Apr 2024 10:00:00 GMT</pubDate>
      <category>架构</category>
      <category>大模型</category>
    </item>
    <item>
      <title>云原生可观测性</title>
      <link>https://www.infoq.cn/article/observability</link>
      <description>&lt;p&gt;聚焦数据库与链路追踪。&lt;/p&gt;</description>
      <pubDate>Tue, 17 Apr 2024 10:00:00 GMT</pubDate>
      <category>云原生</category>
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
        / "infoq_cn"
        / "methods"
        / "api_search.py"
    )
    spec = importlib.util.spec_from_file_location("test_infoq_cn_api_search", module_path)
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


def _query(text: str) -> SubQuery:
    return SubQuery(text=text, rationale="Need Chinese engineering article coverage")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_maps_matching_rss_items_to_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=RSS_FIXTURE, request=request)

    async with _client(handler) as http_client:
        results = await search(_query("LLM 大模型"), http_client=http_client)

    assert len(results) == 2

    first = results[0]
    assert first.url == "https://www.infoq.cn/article/llm-practice"
    assert first.title == "LLM 大模型落地实践"
    assert first.snippet == "企业如何把 LLM 能力接入平台。"
    assert first.content == "企业如何把 LLM 能力接入平台。"
    assert first.source_channel == "infoq_cn:ai"

    second = results[1]
    assert second.url == "https://www.infoq.cn/article/ai-agent"
    assert second.title == "AI Agent 工程化"
    assert second.snippet == "从提示工程到 LLM 系统设计。"
    assert second.content == "从提示工程到 LLM 系统设计。"
    assert second.source_channel == "infoq_cn:架构"


@pytest.mark.asyncio
async def test_search_filters_out_items_missing_all_query_tokens() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=RSS_FIXTURE, request=request)

    async with _client(handler) as http_client:
        results = await search(_query("LLM 架构"), http_client=http_client)

    assert len(results) == 1
    assert results[0].url == "https://www.infoq.cn/article/ai-agent"


@pytest.mark.asyncio
async def test_search_case_insensitive_and_substring_match() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>LLM 平台实践</title>
      <link>https://www.infoq.cn/article/llm-platform</link>
      <description>LLM systems in production.</description>
    </item>
    <item>
      <title>Large Language Model 平台实践</title>
      <link>https://www.infoq.cn/article/large-language-model</link>
      <description>Expanded phrase only.</description>
    </item>
    <item>
      <title>AI 平台实践</title>
      <link>https://www.infoq.cn/article/ai-platform</link>
      <description>Only AI wording.</description>
    </item>
  </channel>
</rss>
"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, request=request)

    async with _client(handler) as http_client:
        results = await search(_query("llm"), http_client=http_client)

    assert [item.url for item in results] == ["https://www.infoq.cn/article/llm-platform"]


@pytest.mark.asyncio
async def test_search_strips_html_and_decodes_entities() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>AI &amp; 数据平台</title>
      <link>https://www.infoq.cn/article/entity-test</link>
      <description>&lt;p&gt;架构&lt;/p&gt;&amp;nbsp;&lt;strong&gt;实践&lt;/strong&gt;</description>
      <category>AI</category>
    </item>
  </channel>
</rss>
"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, request=request)

    async with _client(handler) as http_client:
        results = await search(_query("数据平台"), http_client=http_client)

    assert len(results) == 1
    assert results[0].title == "AI & 数据平台"
    assert results[0].snippet == "架构 实践"


@pytest.mark.asyncio
async def test_search_source_channel_uses_first_category() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>AI 工程系统</title>
      <link>https://www.infoq.cn/article/source-channel</link>
      <description>LLM 与工作流。</description>
      <category>AI</category>
      <category>大模型</category>
    </item>
  </channel>
</rss>
"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rss, request=request)

    async with _client(handler) as http_client:
        results = await search(_query("AI"), http_client=http_client)

    assert len(results) == 1
    assert results[0].source_channel == "infoq_cn:ai"


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error", request=request)

    async with _client(handler) as http_client:
        results = await search(_query("LLM"), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "infoq_cn_search_failed"
    assert "500" in str(logger.events[0][1]["reason"])


@pytest.mark.asyncio
async def test_search_returns_empty_on_bozo_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _Logger()
    monkeypatch.setattr(MODULE, "LOGGER", logger)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<rss><channel><item></rss>", request=request)

    async with _client(handler) as http_client:
        results = await search(_query("LLM"), http_client=http_client)

    assert results == []
    assert logger.events
    assert logger.events[0][0] == "infoq_cn_search_failed"
    assert str(logger.events[0][1]["reason"]) != ""
