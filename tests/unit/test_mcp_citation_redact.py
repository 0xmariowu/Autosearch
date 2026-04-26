"""MCP citation tools must not expose raw signed URLs."""

from __future__ import annotations

import inspect

import pytest

from autosearch.mcp.server import create_server

_SIGNED_URL = "https://bucket.s3.amazonaws.com/key.txt?X-Amz-Signature=abc&keepme=ok"


@pytest.mark.asyncio
async def test_citation_add_redacts_signed_url_in_response() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager
    create = await tm.call_tool("citation_create", {})
    index_id = create["index_id"]

    result = await tm.call_tool(
        "citation_add",
        {"index_id": index_id, "url": _SIGNED_URL},
    )

    assert "X-Amz-Signature" not in result["url"]
    assert "keepme=ok" in result["url"]


@pytest.mark.asyncio
async def test_citation_export_redacts_signed_url_in_markdown() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager
    create = await tm.call_tool("citation_create", {})
    index_id = create["index_id"]
    await tm.call_tool(
        "citation_add",
        {"index_id": index_id, "url": _SIGNED_URL, "title": "Signed URL"},
    )

    result = await tm.call_tool("citation_export", {"index_id": index_id})

    assert "X-Amz-Signature" not in result["markdown"]


def test_citation_export_no_raw_urls_param_at_mcp_boundary() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tool = server._tool_manager.get_tool("citation_export")

    assert tool is not None
    assert "raw_urls" not in inspect.signature(tool.fn).parameters
