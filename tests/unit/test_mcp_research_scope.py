# Self-written, F103 MCP scope surface
import pytest

import autosearch.mcp.server as mcp_server
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.core.pipeline import PipelineResult
from autosearch.core.search_scope import SearchScope


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


class _StubPipeline:
    def __init__(self, result: PipelineResult) -> None:
        self.result = result
        self.calls: list[tuple[str, SearchMode | None, SearchScope | None]] = []

    async def run(
        self,
        query: str,
        mode_hint: SearchMode | None = None,
        *,
        scope: SearchScope | None = None,
    ) -> PipelineResult:
        self.calls.append((query, mode_hint, scope))
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
async def test_research_accepts_scope_params_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    assert await research_tool.run({"query": "test query"}) == "# Test\n\nBody"
    assert pipeline.calls == [("test query", SearchMode.FAST, SearchScope())]


@pytest.mark.asyncio
async def test_research_maps_depth_comprehensive_to_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    await research_tool.run({"query": "test query", "depth": "comprehensive"})
    assert pipeline.calls == [
        ("test query", SearchMode.COMPREHENSIVE, SearchScope(depth="comprehensive"))
    ]


@pytest.mark.asyncio
async def test_research_depth_wins_over_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    await research_tool.run({"query": "test query", "mode": "fast", "depth": "deep"})
    assert pipeline.calls == [("test query", SearchMode.DEEP, SearchScope(depth="deep"))]


@pytest.mark.asyncio
async def test_research_emits_scope_banner_for_nondefault_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    result = await research_tool.run({"query": "test query", "languages": "zh_only"})
    assert result.startswith("[scope] languages=zh_only")


@pytest.mark.asyncio
async def test_research_no_banner_for_default_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    assert await research_tool.run({"query": "test query"}) == "# Test\n\nBody"


@pytest.mark.asyncio
async def test_research_html_format_wraps_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    result = await research_tool.run({"query": "test query", "output_format": "html"})
    assert result.startswith("<!doctype html>")
