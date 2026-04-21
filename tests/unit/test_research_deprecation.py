"""Test that the legacy research() MCP tool emits a DeprecationWarning."""

from __future__ import annotations

import warnings

import pytest

from autosearch.mcp.server import create_server


class _StubPipeline:
    """Minimal pipeline stub that satisfies factory() signature without running anything real."""

    async def run(self, *args, **kwargs):
        # Minimal result that ResearchResponse can serialize without issues.
        raise RuntimeError("stub pipeline — not actually invoked in this test")


@pytest.mark.asyncio
async def test_research_emits_deprecation_warning() -> None:
    """Calling the legacy research() MCP tool must emit a DeprecationWarning."""
    server = create_server(pipeline_factory=lambda: _StubPipeline())  # type: ignore[arg-type]
    tm = server._tool_manager  # noqa: SLF001

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # The stub raises inside; research() catches and returns error response,
        # but the warning is emitted before the pipeline call.
        await tm.call_tool(
            "research",
            {"query": "anything", "mode": "fast"},
        )

    deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecation_warnings) >= 1, "research() must emit a DeprecationWarning"
    message = str(deprecation_warnings[0].message)
    assert "deprecated" in message.lower()
    assert "list_skills" in message
    assert "run_clarify" in message
    assert "run_channel" in message
    assert "migration" in message.lower() or "docs/migration" in message


@pytest.mark.asyncio
async def test_server_instructions_mention_tool_supplier_trio() -> None:
    """The MCP server instructions should steer runtimes toward the v2 trio."""
    server = create_server(pipeline_factory=lambda: _StubPipeline())  # type: ignore[arg-type]
    instructions = server.instructions or ""
    assert "list_skills" in instructions
    assert "run_clarify" in instructions
    assert "run_channel" in instructions
    assert "deprecated" in instructions.lower() or "legacy" in instructions.lower()
