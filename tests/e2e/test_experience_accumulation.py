"""G5-T4: E2E experience accumulation — 10 runs trigger compact, digest injected (all mock)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from autosearch.core.models import Evidence, SubQuery
from autosearch.skills import experience as exp_mod


def _ev(i: int) -> Evidence:
    return Evidence(
        url=f"https://arxiv.org/abs/240{i}.12345",
        title=f"LLM paper {i}",
        snippet="abstract",
        source_channel="arxiv",
        fetched_at=datetime.now(UTC),
        score=0.75,
    )


class _MockArxiv:
    name = "arxiv"
    languages = ["en"]

    async def search(self, q: SubQuery) -> list[Evidence]:
        return [_ev(i) for i in range(8)]


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_experience_accumulates_and_compacts(tmp_path, monkeypatch):
    """Run same channel 10+ times → patterns.jsonl grows → compact triggers → experience.md generated."""
    # Point experience layer at tmp_path
    skill_dir = tmp_path / "channels" / "arxiv"
    skill_dir.mkdir(parents=True)
    monkeypatch.setattr(exp_mod, "_SKILLS_ROOT", tmp_path)
    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(tmp_path))

    with (
        patch("autosearch.mcp.server._build_channels", return_value=[_MockArxiv()]),
        patch("autosearch.mcp.server.Clarifier"),
        patch("autosearch.mcp.server.LLMClient"),
    ):
        from autosearch.mcp.server import create_server

        server = create_server()
        tm = server._tool_manager

        # Run 1: no experience.md yet → rationale has no [Experience Digest]
        # (capture is via _MockArxiv.last_query — not tracked here, tested in G2-T13)

        # Run channel 10 times to accumulate events
        queries = [
            "RAG evaluation 2024",
            "LLM benchmark survey",
            "context window length",
            "chain of thought prompting",
            "retrieval augmented generation",
            "RLHF training",
            "instruction tuning methods",
            "model alignment techniques",
            "safety evaluation",
            "evaluation contamination",
        ]
        for q in queries:
            result = await tm.call_tool(
                "run_channel",
                {
                    "channel_name": "arxiv",
                    "query": q,
                    "rationale": "e2e accumulation test",
                },
            )
            assert result.ok is True

        # After 10 runs: patterns.jsonl should have 10 entries
        patterns_path = skill_dir / "experience" / "patterns.jsonl"
        assert patterns_path.exists(), "patterns.jsonl must be created after first run"
        lines = patterns_path.read_text().strip().splitlines()
        assert len(lines) == 10, f"Expected 10 events, got {len(lines)}"

        # compact() should have been triggered (threshold = 10 events)
        experience_md = skill_dir / "experience.md"
        assert experience_md.exists(), "experience.md must be created after 10 runs trigger compact"
        md_text = experience_md.read_text()
        assert "# arxiv experience" in md_text
        assert len(md_text.splitlines()) <= 120, "experience.md must be <= 120 lines"

        # Run 11: rationale should now contain [Experience Digest]
        class _CapturingArxiv:
            name = "arxiv"
            languages = ["en"]
            last_rationale: str = ""

            async def search(self, q: SubQuery) -> list[Evidence]:
                _CapturingArxiv.last_rationale = q.rationale
                return [_ev(99)]

        # Drop the runtime cached during the first batch so the new mock is
        # actually consulted on the next `run_channel` call.
        from autosearch.core.channel_runtime import reset_channel_runtime

        reset_channel_runtime()
        with patch("autosearch.mcp.server._build_channels", return_value=[_CapturingArxiv()]):
            server2 = create_server()
            await server2._tool_manager.call_tool(
                "run_channel",
                {
                    "channel_name": "arxiv",
                    "query": "embedding models comparison",
                    "rationale": "base rationale",
                },
            )

        assert "[Experience Digest]" in _CapturingArxiv.last_rationale, (
            "After compact, the 11th run must inject [Experience Digest] into rationale"
        )


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_experience_not_injected_before_first_run(tmp_path, monkeypatch):
    """Before any runs: no experience.md → rationale has no [Experience Digest]."""
    skill_dir = tmp_path / "channels" / "arxiv"
    skill_dir.mkdir(parents=True)
    monkeypatch.setattr(exp_mod, "_SKILLS_ROOT", tmp_path)
    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(tmp_path))

    captured = []

    class _TrackingArxiv:
        name = "arxiv"
        languages = ["en"]

        async def search(self, q: SubQuery) -> list[Evidence]:
            captured.append(q.rationale)
            return [_ev(1)]

    with (
        patch("autosearch.mcp.server._build_channels", return_value=[_TrackingArxiv()]),
        patch("autosearch.mcp.server.Clarifier"),
        patch("autosearch.mcp.server.LLMClient"),
    ):
        from autosearch.mcp.server import create_server

        server = create_server()
        await server._tool_manager.call_tool(
            "run_channel",
            {
                "channel_name": "arxiv",
                "query": "test",
                "rationale": "clean start",
            },
        )

    assert captured, "channel must have been called"
    assert "[Experience Digest]" not in captured[0], (
        "Before any experience exists, rationale must not contain [Experience Digest]"
    )
