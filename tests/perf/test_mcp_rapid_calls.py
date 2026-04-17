# Self-written, plan v2.3 § 13.5
import time

import pytest

import autosearch.mcp.server as mcp_server
from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.core.pipeline import PipelineResult


def _ok_result() -> PipelineResult:
    return PipelineResult(
        status="ok",
        clarification=ClarifyResult(
            need_clarification=False,
            question=None,
            verification="Enough information to proceed.",
            rubrics=[],
            mode=SearchMode.FAST,
        ),
        markdown="# Perf\n\nRapid MCP response.",
        iterations=1,
    )


class _ImmediatePipeline:
    def __init__(self, result: PipelineResult) -> None:
        self.result = result
        self.calls: list[tuple[str, SearchMode | None]] = []

    async def run(
        self,
        query: str,
        mode_hint: SearchMode | None = None,
    ) -> PipelineResult:
        self.calls.append((query, mode_hint))
        return self.result


@pytest.mark.perf
@pytest.mark.asyncio
async def test_research_tool_handles_twenty_rapid_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = _ImmediatePipeline(result=_ok_result())
    monkeypatch.setattr(mcp_server, "_default_pipeline_factory", lambda: pipeline)
    server = mcp_server.create_server()

    research_tool = server._tool_manager.get_tool("research")

    assert research_tool is not None

    started_at = time.perf_counter()
    outputs = [
        await research_tool.run({"query": f"rapid call {index}", "mode": "fast"})
        for index in range(20)
    ]
    elapsed = time.perf_counter() - started_at

    assert len(outputs) == 20
    assert all(output for output in outputs)
    assert elapsed < 3.0
    assert pipeline.calls == [(f"rapid call {index}", SearchMode.FAST) for index in range(20)]
