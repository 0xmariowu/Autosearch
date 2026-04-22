"""G5-T1: E2E fast path — clear query, no clarification needed (all mock)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from autosearch.core.models import ClarifyResult, Evidence, SearchMode, SubQuery
from autosearch.mcp.server import create_server


_EVIDENCE = [
    Evidence(
        url="https://github.com/duckdb/duckdb/issues/1234",
        title="HNSW index memory usage",
        snippet="Memory usage details for DuckDB HNSW",
        source_channel="github",
        fetched_at=datetime.now(UTC),
        score=0.8,
    ),
    Evidence(
        url="https://stackoverflow.com/q/12345",
        title="DuckDB vector search limitations",
        snippet="Known limitations of DuckDB vector search",
        source_channel="stackoverflow",
        fetched_at=datetime.now(UTC),
        score=0.7,
    ),
]


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_fast_path_no_clarification(monkeypatch):
    """Clear query: need_clarification=False → skip Step 0, run channels, get citations."""
    mock_result = ClarifyResult(
        need_clarification=False,
        verification="ok",
        rubrics=[],
        mode=SearchMode.FAST,
        channel_priority=["github", "stackoverflow"],
        channel_skip=[],
    )

    class _MockClarifier:
        async def clarify(self, *a, **kw):
            return mock_result

    class _MockChannel:
        def __init__(self, name):
            self.name = name
            self.languages = ["en"]

        async def search(self, q: SubQuery) -> list[Evidence]:
            return [e for e in _EVIDENCE if e.source_channel == self.name]

    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")

    with (
        patch(
            "autosearch.mcp.server._build_channels",
            return_value=[
                _MockChannel("github"),
                _MockChannel("stackoverflow"),
            ],
        ),
        patch("autosearch.mcp.server.Clarifier", return_value=_MockClarifier()),
        patch("autosearch.mcp.server.LLMClient"),
    ):
        server = create_server()
        tm = server._tool_manager

        # Step 1: clarify
        clarify_resp = await tm.call_tool(
            "run_clarify", {"query": "DuckDB HNSW vector limitations"}
        )
        assert clarify_resp.need_clarification is False
        assert clarify_resp.channel_priority == ["github", "stackoverflow"]

        # Step 2: select channels
        channels_resp = await tm.call_tool(
            "select_channels_tool", {"query": "DuckDB HNSW vector limitations"}
        )
        assert len(channels_resp["channels"]) >= 1

        # Step 3: create citation index + loop
        idx = await tm.call_tool("citation_create", {})
        index_id = idx["index_id"]
        loop = await tm.call_tool("loop_init", {})
        state_id = loop["state_id"]

        # Step 4: run channels
        all_evidence = []
        for ch_name in ["github", "stackoverflow"]:
            result = await tm.call_tool(
                "run_channel", {"channel_name": ch_name, "query": "DuckDB HNSW"}
            )
            if result.ok:
                all_evidence.extend(result.evidence)
                for ev in result.evidence:
                    await tm.call_tool(
                        "citation_add",
                        {
                            "index_id": index_id,
                            "url": ev["url"],
                            "title": ev.get("title", ""),
                            "source": ch_name,
                        },
                    )

        await tm.call_tool(
            "loop_update",
            {
                "state_id": state_id,
                "evidence": all_evidence,
                "query": "DuckDB HNSW",
            },
        )

        # Step 5: export citations
        refs = await tm.call_tool("citation_export", {"index_id": index_id})
        assert refs["count"] >= 1
        assert "[1]" in refs["markdown"]
