# Self-written, plan v2.3 § 13.5
import pytest
from mcp.server.fastmcp import FastMCP

import autosearch.mcp.server as mcp_server
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.core.models import PipelineResult


@pytest.fixture(autouse=True)
def _enable_legacy_research(monkeypatch: pytest.MonkeyPatch) -> None:
    """W3.3 PR A: enable the legacy research() path for these tests."""
    monkeypatch.setenv("AUTOSEARCH_LEGACY_RESEARCH", "1")


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
    research = next(tool for tool in tools if tool.name == "research")
    assert research.outputSchema is not None
    assert set(research.outputSchema["properties"]) >= {
        "content",
        "delivery_status",
        "channel_empty_calls",
        "routing_trace",
        "scope",
    }


@pytest.mark.asyncio
async def test_research_tool_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    result = await research_tool.run({"query": "test query", "mode": "fast"})
    assert isinstance(result, mcp_server.ResearchResponse)
    assert result.content == "# Test\n\nBody"
    assert result.delivery_status == "ok"
    assert result.channel_empty_calls == {}
    assert result.routing_trace == {}
    assert result.scope == {
        "domain_followups": [],
        "channel_scope": "all",
        "depth": "fast",
        "output_format": "md",
    }
    assert pipeline.calls == [("test query", SearchMode.FAST)]


@pytest.mark.asyncio
async def test_research_tool_success_path_content_is_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    result = await research_tool.run({"query": "test query", "mode": "fast"})
    assert result.content == "# Test\n\nBody"
    assert result.delivery_status == "ok"


@pytest.mark.asyncio
async def test_research_tool_clarification_path_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_clarification_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    result = await research_tool.run({"query": "test query", "mode": "deep"})
    assert isinstance(result, mcp_server.ResearchResponse)
    assert result.content == "[clarification needed] Which deployment target matters most?"
    assert result.delivery_status == "needs_clarification"
    assert pipeline.calls == [("test query", SearchMode.DEEP)]


@pytest.mark.asyncio
async def test_research_tool_error_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(exc=RuntimeError("boom"))
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    result = await research_tool.run({"query": "test query", "mode": "fast"})
    assert isinstance(result, mcp_server.ResearchResponse)
    assert result.content.startswith("[error]")
    assert result.content == "[error] boom"
    assert result.delivery_status == "error"
    assert pipeline.calls == [("test query", SearchMode.FAST)]


@pytest.mark.asyncio
async def test_research_response_serializable_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _StubPipeline(result=_ok_result())
    _install_default_factory(monkeypatch, pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None
    result = await research_tool.run({"query": "test query", "mode": "fast"})
    payload = result.model_dump()
    encoded = result.model_dump_json()
    decoded = mcp_server.ResearchResponse.model_validate_json(encoded)

    assert payload["content"] == "# Test\n\nBody"
    assert payload["delivery_status"] == "ok"
    assert decoded == result


@pytest.mark.asyncio
async def test_health_tool_returns_structured_snapshot() -> None:
    """Per plan §P1-5: health() must return a structured snapshot, not just
    'ok'. Includes version, tool counts, channel counts, secrets-file presence
    (key NAMES only, never values), and the runtime ChannelHealth snapshot."""
    server = mcp_server.create_server()

    health_tool = server._tool_manager.get_tool("health")
    assert health_tool is not None

    result = await health_tool.run({})
    assert isinstance(result, dict), f"expected dict snapshot, got {type(result).__name__}"
    assert result.get("ok") is True
    assert "version" in result
    assert "tool_count" in result and result["tool_count"] >= 10
    assert "required_tools_present" in result
    assert "channels" in result
    assert "secrets_file" in result
    assert "channel_health_snapshot" in result
