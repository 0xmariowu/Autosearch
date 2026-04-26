"""Test that the legacy research() MCP tool emits a DeprecationWarning."""

from __future__ import annotations

import warnings

import pytest

from autosearch.mcp.server import create_server


_FAKE_SECRET = "sk-" + "FAKEKEY1234567890abcdef"


class _StubPipeline:
    """Minimal pipeline stub that satisfies factory() signature without running anything real."""

    async def run(self, *args, **kwargs):
        # Minimal result that ResearchResponse can serialize without issues.
        raise RuntimeError("stub pipeline — not actually invoked in this test")


class _SecretFailingPipeline:
    async def run(self, *args, **kwargs):
        raise RuntimeError(f"upstream failed with key {_FAKE_SECRET}")


@pytest.mark.asyncio
async def test_research_emits_deprecation_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """When opted in via AUTOSEARCH_LEGACY_RESEARCH=1, calling research() must
    still emit a DeprecationWarning so users know they're on a sunset path."""
    monkeypatch.setenv("AUTOSEARCH_LEGACY_RESEARCH", "1")
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
async def test_research_tool_not_registered_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plan §P1-4: by default the deprecated research tool is not registered
    at all — host agents only see it if AUTOSEARCH_LEGACY_RESEARCH=1 opts in.

    Previous behavior was "registered but returns deprecation response"; that
    still let LLMs choose the attractive `research` tool name and waste a turn.
    """
    monkeypatch.delenv("AUTOSEARCH_LEGACY_RESEARCH", raising=False)

    server = create_server(pipeline_factory=lambda: _StubPipeline())  # type: ignore[arg-type]
    tools = await server.list_tools()
    tool_names = {tool.name for tool in tools}
    assert "research" not in tool_names, (
        f"research must not register without opt-in (got: {sorted(tool_names)})"
    )


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


@pytest.mark.asyncio
async def test_legacy_research_exception_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy research() errors must not expose secret-shaped exception text."""
    secret = _FAKE_SECRET
    monkeypatch.setenv("AUTOSEARCH_LEGACY_RESEARCH", "1")

    from autosearch.mcp.server import ResearchResponse

    server = create_server(pipeline_factory=lambda: _SecretFailingPipeline())  # type: ignore[arg-type]
    tm = server._tool_manager  # noqa: SLF001

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        response = await tm.call_tool(
            "research",
            {"query": "anything", "mode": "fast"},
        )

    assert isinstance(response, ResearchResponse)
    assert response.delivery_status == "error"
    assert secret not in response.content
    assert "[REDACTED]" in response.content
