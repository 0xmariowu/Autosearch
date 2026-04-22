"""G5-T2: E2E clarify path — ambiguous query triggers one clarifying question (all mock)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from autosearch.core.models import ClarifyResult, Evidence, SearchMode, SubQuery


_EVIDENCE_ZH = [
    Evidence(
        url="https://xiaohongshu.com/post/xgp-hk-review",
        title="香港XGP值得买吗？亲测体验",
        snippet="香港XGP订阅详细评测",
        source_channel="xiaohongshu",
        fetched_at=datetime.now(UTC),
        score=0.85,
    ),
]


class _MockClarifierFirstAmbiguous:
    """First call returns need_clarification=True; second call returns False."""

    def __init__(self):
        self._call_count = 0

    async def clarify(self, request, *a, **kw):
        self._call_count += 1
        if self._call_count == 1:
            return ClarifyResult(
                need_clarification=True,
                question="你想了解哪个区的 XGP？",
                question_options=["香港区", "国服", "香港 vs 国服对比"],
                rubrics=[],
                mode=SearchMode.FAST,
            )
        return ClarifyResult(
            need_clarification=False,
            verification="明白了，搜香港区XGP订阅",
            rubrics=[],
            mode=SearchMode.FAST,
            channel_priority=["xiaohongshu", "zhihu"],
            channel_skip=[],
        )


class _MockZhChannel:
    def __init__(self, name):
        self.name = name
        self.languages = ["zh"]

    async def search(self, q: SubQuery) -> list[Evidence]:
        return _EVIDENCE_ZH


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_clarify_path_ask_once_then_proceed(monkeypatch):
    """Ambiguous query: ask once → user answers → proceed to search without asking again."""
    mock_clarifier = _MockClarifierFirstAmbiguous()

    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")

    with (
        patch(
            "autosearch.mcp.server._build_channels",
            return_value=[
                _MockZhChannel("xiaohongshu"),
                _MockZhChannel("zhihu"),
            ],
        ),
        patch("autosearch.mcp.server.Clarifier", return_value=mock_clarifier),
        patch("autosearch.mcp.server.LLMClient"),
    ):
        from autosearch.mcp.server import create_server

        server = create_server()
        tm = server._tool_manager

        # First call: should trigger clarification
        resp1 = await tm.call_tool("run_clarify", {"query": "XGP 怎么买"})
        assert resp1.need_clarification is True
        assert resp1.question
        assert resp1.question_options == ["香港区", "国服", "香港 vs 国服对比"]

        # Simulate user answering "香港区" → re-call with enriched query
        resp2 = await tm.call_tool("run_clarify", {"query": "XGP 怎么买 - 香港区"})
        assert resp2.need_clarification is False
        assert "xiaohongshu" in resp2.channel_priority

        # Total clarifier calls = 2 (asked once, answered once)
        assert mock_clarifier._call_count == 2

        # Proceed to search with priority channels
        idx = await tm.call_tool("citation_create", {})
        result = await tm.call_tool(
            "run_channel",
            {
                "channel_name": "xiaohongshu",
                "query": "XGP 香港区 订阅",
            },
        )
        assert result.ok is True
        assert len(result.evidence) >= 1

        # Add to citations
        for ev in result.evidence:
            await tm.call_tool(
                "citation_add",
                {
                    "index_id": idx["index_id"],
                    "url": ev["url"],
                    "title": ev.get("title", ""),
                    "source": "xiaohongshu",
                },
            )

        refs = await tm.call_tool("citation_export", {"index_id": idx["index_id"]})
        assert refs["count"] >= 1


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_no_clarification_needed_skips_step0(monkeypatch):
    """Clear query: no clarification, Step 0 skipped entirely."""
    clear_result = ClarifyResult(
        need_clarification=False,
        verification="clear query, proceeding",
        rubrics=[],
        mode=SearchMode.FAST,
        channel_priority=["arxiv"],
        channel_skip=[],
    )

    class _ClearClarifier:
        async def clarify(self, *a, **kw):
            return clear_result

    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")

    with (
        patch("autosearch.mcp.server.Clarifier", return_value=_ClearClarifier()),
        patch("autosearch.mcp.server.LLMClient"),
        patch("autosearch.mcp.server._build_channels", return_value=[]),
    ):
        from autosearch.mcp.server import create_server

        server = create_server()
        tm = server._tool_manager

        resp = await tm.call_tool("run_clarify", {"query": "DuckDB HNSW vector search PR numbers"})
        assert resp.need_clarification is False
        assert not resp.question
        assert not resp.question_options
