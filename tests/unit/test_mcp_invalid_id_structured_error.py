"""Bug 6 (fix-plan): citation_* and loop_* MCP tools used to raise FastMCP
ToolError on an invalid index_id / state_id, breaking the host agent's
workflow. They must instead return a structured response the agent can
recognize and recover from."""

from __future__ import annotations

import pytest

from autosearch.mcp.server import create_server


@pytest.mark.asyncio
async def test_citation_add_invalid_index_returns_structured_error() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager
    result = await tm.call_tool(
        "citation_add",
        {"index_id": "does-not-exist", "url": "https://example.com"},
    )
    assert result["ok"] is False
    assert result["reason"] == "invalid_index_id"
    assert result["index_id"] == "does-not-exist"


@pytest.mark.asyncio
async def test_citation_export_invalid_index_returns_structured_error() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager
    result = await tm.call_tool("citation_export", {"index_id": "ghost"})
    assert result["ok"] is False
    assert result["reason"] == "invalid_index_id"


@pytest.mark.asyncio
async def test_citation_merge_invalid_target_returns_structured_error() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager
    create = await tm.call_tool("citation_create", {})
    real_id = create["index_id"]
    result = await tm.call_tool(
        "citation_merge",
        {"target_id": "ghost-target", "source_id": real_id},
    )
    assert result["ok"] is False
    assert result["reason"] == "invalid_target_id"


@pytest.mark.asyncio
async def test_loop_update_invalid_state_returns_structured_error() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager
    result = await tm.call_tool(
        "loop_update",
        {"state_id": "no-such-loop", "evidence": [], "query": "x"},
    )
    assert result["ok"] is False
    assert result["reason"] == "invalid_state_id"


@pytest.mark.asyncio
async def test_loop_get_gaps_invalid_state_returns_structured_error() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager
    result = await tm.call_tool("loop_get_gaps", {"state_id": "no-such-loop"})
    assert result["ok"] is False
    assert result["reason"] == "invalid_state_id"


@pytest.mark.asyncio
async def test_loop_add_gap_invalid_state_returns_structured_error() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager
    result = await tm.call_tool("loop_add_gap", {"state_id": "no-such-loop", "gap": "topic"})
    assert result["ok"] is False
    assert result["reason"] == "invalid_state_id"


@pytest.mark.asyncio
async def test_valid_citation_workflow_still_works() -> None:
    """Sanity: error-handling wrapper must not break the happy path."""
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager
    create = await tm.call_tool("citation_create", {})
    idx = create["index_id"]
    add = await tm.call_tool(
        "citation_add",
        {"index_id": idx, "url": "https://arxiv.org/abs/x"},
    )
    assert add.get("ok") is not False
    assert add["citation_number"] == 1
    export = await tm.call_tool("citation_export", {"index_id": idx})
    assert export.get("ok") is not False
    assert export["count"] == 1
