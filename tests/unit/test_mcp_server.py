# Self-written, plan v2.3 § 13.5
import pytest
from mcp.server.fastmcp import FastMCP

import autosearch.mcp.server as mcp_server
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.core.pipeline import PipelineResult


def _ok_result() -> PipelineResult:
    return PipelineResult(
        delivery_status="ok",
        clarification=ClarifyResult(
            need_clarification=False,
            question=None,
            verification="Enough information to proceed.",
            rubrics=[],
            mode=SearchMode.FAST,
        ),
        markdown="# Test\n\nBody",
        iterations=1,
    )


def _clarification_result() -> PipelineResult:
    return PipelineResult(
        delivery_status="needs_clarification",
        clarification=ClarifyResult(
            need_clarification=True,
            question="Which deployment target matters most?",
            verification=None,
            rubrics=[],
            mode=SearchMode.DEEP,
        ),
        iterations=0,
    )


class _StubPipeline:
    def __init__(
        self,
        result: PipelineResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.result = result
        self.exc = exc
        self.calls: list[tuple[str, SearchMode | None]] = []

    async def run(
        self,
        query: str,
        mode_hint: SearchMode | None = None,
        *,
        scope=None,
    ) -> PipelineResult:
        _ = scope
        self.calls.append((query, mode_hint))
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result


def _install_default_factory(
    monkeypatch: pytest.MonkeyPatch,
    pipeline: _StubPipeline,
) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_default_pipeline_factory",
        lambda: pipeline,
    )


@pytest.mark.asyncio
async def test_create_server_returns_fastmcp_named_autosearch() -> None:
    server = mcp_server.create_server()

    assert isinstance(server, FastMCP)
    assert server.name == "autosearch"


@pytest.mark.asyncio
async def test_create_server_registers_research_tool() -> None:
    server = mcp_server.create_server()

    tools = await server.list_tools()

    assert {tool.name for tool in tools} >= {"research", "health"}


@pytest.mark.asyncio
async def test_research_tool_returns_markdown_for_ok_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    assert await research_tool.run({"query": "test query", "mode": "fast"}) == "# Test\n\nBody"
    assert pipeline.calls == [("test query", SearchMode.FAST)]


@pytest.mark.asyncio
async def test_research_tool_returns_clarification_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_clarification_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    result = await research_tool.run({"query": "test query", "mode": "deep"})
    assert result.startswith("[clarification needed]")
    assert pipeline.calls == [("test query", SearchMode.DEEP)]


@pytest.mark.asyncio
async def test_research_tool_returns_error_prefix_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(exc=RuntimeError("boom"))
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    assert await research_tool.run({"query": "test query", "mode": "fast"}) == "[error] boom"
    assert pipeline.calls == [("test query", SearchMode.FAST)]


@pytest.mark.asyncio
async def test_health_tool_returns_ok() -> None:
    server = mcp_server.create_server()

    health_tool = server._tool_manager.get_tool("health")

    assert health_tool is not None
    assert await health_tool.run({}) == "ok"
