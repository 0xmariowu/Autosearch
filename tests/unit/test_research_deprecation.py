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


@pytest.mark.asyncio
async def test_research_default_returns_deprecation_without_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """W3.3 PR A: default (no AUTOSEARCH_LEGACY_RESEARCH env) must NOT invoke the pipeline.

    The research() tool should return a ResearchResponse with:
    - delivery_status == "deprecated"
    - content mentions the trio
    - routing_trace indicates deprecation

    The Pipeline factory is set to a stub that would raise if called. If research()
    is properly short-circuited, the test passes without triggering the stub.
    """
    monkeypatch.delenv("AUTOSEARCH_LEGACY_RESEARCH", raising=False)

    from autosearch.mcp.server import ResearchResponse

    server = create_server(pipeline_factory=lambda: _StubPipeline())  # type: ignore[arg-type]
    tm = server._tool_manager  # noqa: SLF001

    import warnings as _warnings

    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        response = await tm.call_tool(
            "research",
            {"query": "anything", "mode": "fast"},
        )

    assert isinstance(response, ResearchResponse)
    assert response.delivery_status == "deprecated"
    assert "deprecated" in response.content.lower()
    assert "list_skills" in response.content
    assert "run_clarify" in response.content
    assert "run_channel" in response.content
    assert response.routing_trace.get("deprecated") is True


@pytest.mark.asyncio
async def test_research_legacy_env_opt_in_restores_pipeline_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting AUTOSEARCH_LEGACY_RESEARCH=1 must restore the legacy pipeline invocation."""
    monkeypatch.setenv("AUTOSEARCH_LEGACY_RESEARCH", "1")

    from autosearch.mcp.server import ResearchResponse

    # Stub pipeline that raises — so if legacy path is taken, we reach the except
    # branch and get delivery_status="error" with the stub's error message.
    server = create_server(pipeline_factory=lambda: _StubPipeline())  # type: ignore[arg-type]
    tm = server._tool_manager  # noqa: SLF001

    import warnings as _warnings

    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        response = await tm.call_tool(
            "research",
            {"query": "anything", "mode": "fast"},
        )

    assert isinstance(response, ResearchResponse)
    # The stub raises, so research() should catch and return an error response —
    # NOT a deprecation response. This proves the legacy code path ran.
    assert response.delivery_status == "error"
    assert "stub pipeline" in response.content.lower()
