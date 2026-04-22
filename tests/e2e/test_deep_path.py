"""G5-T3: E2E deep path — loop state + parallel delegation + citations (all mock)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from autosearch.core.models import ClarifyResult, Evidence, SearchMode, SubQuery



def _ev(url: str, title: str, ch: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet="...",
        source_channel=ch,
        fetched_at=datetime.now(UTC),
        score=0.7,
    )


_EVIDENCE_BY_CHANNEL = {
    "github": [
        _ev(
            "https://github.com/anthropics/claude-code/issues/42",
            "hooks API breaking change",
            "github",
        ),
        _ev(
            "https://github.com/anthropics/claude-code/issues/99",
            "settings.json migration guide",
            "github",
        ),
    ],
    "hackernews": [
        _ev("https://news.ycombinator.com/item?id=111", "Claude Code settings 2026", "hackernews"),
    ],
    "devto": [
        _ev("https://dev.to/example/claude-hooks-2026", "Claude Code Hooks Tutorial 2026", "devto"),
    ],
}


class _MockDeepClarifier:
    async def clarify(self, *a, **kw):
        from autosearch.core.models import Rubric  # noqa: PLC0415

        return ClarifyResult(
            need_clarification=False,
            verification="ok",
            rubrics=[
                Rubric(text="Must include issue numbers"),
                Rubric(text="Must cover 2025-2026 timeframe"),
            ],
            mode=SearchMode.DEEP,
            channel_priority=["github", "hackernews", "devto"],
            channel_skip=[],
        )


class _MockChannel:
    def __init__(self, name):
        self.name = name
        self.languages = ["en"]

    async def search(self, q: SubQuery) -> list[Evidence]:
        return _EVIDENCE_BY_CHANNEL.get(self.name, [])


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_deep_path_loop_and_citations(monkeypatch):
    """Deep mode: loop_init → delegate_subtask → loop_update → gaps → citation → export."""
    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")

    mock_channels = [_MockChannel("github"), _MockChannel("hackernews"), _MockChannel("devto")]

    with (
        patch("autosearch.mcp.server._build_channels", return_value=mock_channels),
        patch("autosearch.core.channel_bootstrap._build_channels", return_value=mock_channels),
        patch("autosearch.mcp.server.Clarifier", return_value=_MockDeepClarifier()),
        patch("autosearch.mcp.server.LLMClient"),
    ):
        from autosearch.mcp.server import create_server

        server = create_server()
        tm = server._tool_manager

        # Step 1: clarify → deep mode
        clarify = await tm.call_tool(
            "run_clarify", {"query": "Claude Code settings.json 2026 breaking changes"}
        )
        assert clarify.mode == "deep"

        # Step 2: initialize loop + citation index
        loop = await tm.call_tool("loop_init", {})
        state_id = loop["state_id"]
        idx = await tm.call_tool("citation_create", {})
        index_id = idx["index_id"]

        # Step 3: delegate subtask (parallel multi-channel)
        delegation = await tm.call_tool(
            "delegate_subtask",
            {
                "task_description": "Find Claude Code settings.json breaking changes 2026",
                "channels": ["github", "hackernews", "devto"],
                "query": "Claude Code settings.json breaking changes 2026",
                "max_per_channel": 5,
            },
        )
        assert delegation["summary"]
        assert len(delegation["evidence_by_channel"]) >= 1

        # Step 4: update loop state, check gaps
        all_ev = [ev for evs in delegation["evidence_by_channel"].values() for ev in evs]
        loop_state = await tm.call_tool(
            "loop_update",
            {
                "state_id": state_id,
                "evidence": all_ev,
                "query": "Claude Code settings.json",
            },
        )
        assert loop_state["round_count"] == 1
        assert len(loop_state["visited_urls"]) >= 1

        # Add a gap manually
        await tm.call_tool(
            "loop_add_gap", {"state_id": state_id, "gap": "missing pre-2025 migration docs"}
        )
        gaps = await tm.call_tool("loop_get_gaps", {"state_id": state_id})
        assert "missing pre-2025 migration docs" in gaps["gaps"]

        # Step 5: add evidence to citation index
        for ev in all_ev[:5]:
            await tm.call_tool(
                "citation_add",
                {
                    "index_id": index_id,
                    "url": ev["url"],
                    "title": ev.get("title", ""),
                    "source": ev.get("source_channel", ""),
                },
            )

        # Step 6: merge and export
        refs = await tm.call_tool("citation_export", {"index_id": index_id})
        assert refs["count"] >= 2
        assert "[1]" in refs["markdown"]
        assert "[2]" in refs["markdown"]

        # Step 7: recent signal fusion — filter to last 90 days
        filtered = await tm.call_tool(
            "recent_signal_fusion",
            {
                "evidence": all_ev,
                "days": 90,
            },
        )
        # Result may be empty (mock evidence has no dates), that's fine
        assert isinstance(filtered, list)
