"""G4: Live integration tests for free channels (no API key required).

These tests make real network calls. They are marked @pytest.mark.live @pytest.mark.slow
and run in the nightly CI workflow, not on every PR.

Run manually: pytest tests/integration/test_free_channels_live.py -m live -v
"""

from __future__ import annotations

import os

import pytest

from autosearch.channels.base import MethodUnavailable
from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SubQuery


def _get_channel(name: str):
    channels = {c.name: c for c in _build_channels()}
    if name not in channels:
        pytest.skip(f"Channel '{name}' not available in this environment")
    return channels[name]


def _subquery(text: str) -> SubQuery:
    return SubQuery(text=text, rationale=f"live test: {text}")


def _assert_valid_evidence(results, channel_name: str, min_count: int = 1) -> None:
    assert len(results) >= min_count, (
        f"{channel_name}: expected >= {min_count} results, got {len(results)}"
    )
    for ev in results:
        assert ev.url, f"{channel_name}: evidence missing url"
        assert ev.title, f"{channel_name}: evidence missing title"
        # source_channel may include item IDs (e.g. "wikidata:Q123"); check prefix
        assert ev.source_channel.startswith(channel_name), (
            f"{channel_name}: expected source_channel to start with '{channel_name}', got '{ev.source_channel}'"
        )


# ── Free channels (no API key) ───────────────────────────────────────────────


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_arxiv_live():
    ch = _get_channel("arxiv")
    results = await ch.search(_subquery("LLM evaluation methodology 2024"))
    _assert_valid_evidence(results, "arxiv", min_count=3)
    assert any("arxiv.org" in ev.url for ev in results)


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_pubmed_live():
    ch = _get_channel("pubmed")
    results = await ch.search(_subquery("CRISPR gene therapy clinical trial"))
    _assert_valid_evidence(results, "pubmed", min_count=3)
    assert any("pubmed.ncbi.nlm.nih.gov" in ev.url for ev in results)


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_dockerhub_live():
    ch = _get_channel("dockerhub")
    results = await ch.search(_subquery("llm inference server"))
    _assert_valid_evidence(results, "dockerhub", min_count=2)
    assert any("hub.docker.com" in ev.url for ev in results)


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_hackernews_live():
    ch = _get_channel("hackernews")
    results = await ch.search(_subquery("large language model"))
    _assert_valid_evidence(results, "hackernews", min_count=3)


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_wikipedia_live():
    ch = _get_channel("wikidata")
    if ch is None:
        ch = _get_channel("wikipedia")
    results = await ch.search(_subquery("transformer neural network"))
    _assert_valid_evidence(results, ch.name, min_count=1)


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_ddgs_live():
    ch = _get_channel("ddgs")
    results = await ch.search(_subquery("open source AI search tool 2024"))
    _assert_valid_evidence(results, "ddgs", min_count=3)


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_tieba_live():
    """百度贴吧 live test — may be slow or rate-limited from non-CN IPs."""
    ch = _get_channel("tieba")
    results = await ch.search(_subquery("AI 编程助手"))
    _assert_valid_evidence(results, "tieba", min_count=1)
    assert any("tieba.baidu.com" in ev.url for ev in results)


# ── Graceful degradation (no key → MethodUnavailable, not crash) ─────────────


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_searxng_raises_unavailable_when_no_url():
    """searxng must raise MethodUnavailable (not crash) when SEARXNG_URL unset."""
    backup = os.environ.pop("SEARXNG_URL", None)
    try:
        ch = _get_channel("searxng")
        with pytest.raises(MethodUnavailable, match="SEARXNG_URL"):
            await ch.search(_subquery("test query"))
    finally:
        if backup is not None:
            os.environ["SEARXNG_URL"] = backup


@pytest.mark.live
@pytest.mark.slow
@pytest.mark.asyncio
async def test_firecrawl_raises_unavailable_when_no_key():
    """fetch-firecrawl must raise MethodUnavailable when FIRECRAWL_API_KEY unset."""
    backup = os.environ.pop("FIRECRAWL_API_KEY", None)
    try:
        channels = {c.name: c for c in _build_channels()}
        if "fetch-firecrawl" not in channels:
            pytest.skip("fetch-firecrawl channel not available")
        ch = channels["fetch-firecrawl"]
        with pytest.raises(MethodUnavailable):
            await ch.search(_subquery("https://example.com"))
    finally:
        if backup is not None:
            os.environ["FIRECRAWL_API_KEY"] = backup
