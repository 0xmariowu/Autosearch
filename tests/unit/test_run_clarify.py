"""Tests for the run_clarify MCP tool — clarify without running the pipeline."""

from __future__ import annotations

import pytest

from autosearch.core.models import ClarifyRequest, ClarifyResult, Rubric, SearchMode
from autosearch.mcp.server import (
    ClarifyToolResponse,
    _invoke_clarifier,
    create_server,
)


class _FakeClarifier:
    """Controls what Clarifier.clarify() returns or raises."""

    def __init__(self, result_or_exc: ClarifyResult | Exception):
        self._result_or_exc = result_or_exc
        self.last_request: ClarifyRequest | None = None

    async def clarify(self, request, client, *, channels=None):
        self.last_request = request
        if isinstance(self._result_or_exc, Exception):
            raise self._result_or_exc
        return self._result_or_exc


@pytest.mark.asyncio
async def test_run_clarify_tool_is_registered() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tools = await server.list_tools()
    tool_names = {tool.name for tool in tools}
    assert "run_clarify" in tool_names


@pytest.mark.asyncio
async def test_invoke_clarifier_no_clarification_needed() -> None:
    clarifier = _FakeClarifier(
        ClarifyResult(
            need_clarification=False,
            question=None,
            verification="Got it. Starting research now.",
            rubrics=[
                Rubric(text="covers recent last 30 days"),
                Rubric(text="cites primary sources"),
            ],
            mode=SearchMode.DEEP,
            query_type="product-research",
            channel_priority=["bilibili", "xiaohongshu"],
            channel_skip=["reddit"],
        )
    )

    response = await _invoke_clarifier(
        query="XGP 香港服区别",
        mode_hint=SearchMode.DEEP,
        clarifier=clarifier,  # type: ignore[arg-type]
        llm=object(),  # type: ignore[arg-type]  # not called on happy path
        channels=[],
    )

    assert response.ok is True
    assert response.need_clarification is False
    assert response.question is None
    assert response.verification == "Got it. Starting research now."
    assert response.mode == "deep"
    assert response.query_type == "product-research"
    assert response.rubrics == ["covers recent last 30 days", "cites primary sources"]
    assert response.channel_priority == ["bilibili", "xiaohongshu"]
    assert response.channel_skip == ["reddit"]
    assert clarifier.last_request is not None
    assert clarifier.last_request.query == "XGP 香港服区别"
    assert clarifier.last_request.mode_hint == SearchMode.DEEP


@pytest.mark.asyncio
async def test_invoke_clarifier_clarification_needed() -> None:
    clarifier = _FakeClarifier(
        ClarifyResult(
            need_clarification=True,
            question="Which region's XGP do you want to compare?",
            verification=None,
            rubrics=[],
            mode=SearchMode.FAST,
            query_type=None,
            channel_priority=[],
            channel_skip=[],
        )
    )

    response = await _invoke_clarifier(
        query="XGP 有什么区别",
        mode_hint=None,
        clarifier=clarifier,  # type: ignore[arg-type]
        llm=object(),  # type: ignore[arg-type]
        channels=[],
    )

    assert response.ok is True
    assert response.need_clarification is True
    assert response.question == "Which region's XGP do you want to compare?"
    assert response.verification is None
    assert response.mode == "fast"


@pytest.mark.asyncio
async def test_invoke_clarifier_propagates_as_structured_error() -> None:
    clarifier = _FakeClarifier(RuntimeError("llm unreachable"))

    response = await _invoke_clarifier(
        query="anything",
        mode_hint=None,
        clarifier=clarifier,  # type: ignore[arg-type]
        llm=object(),  # type: ignore[arg-type]
        channels=[],
    )

    assert response.ok is False
    assert response.need_clarification is False
    assert "clarify_error" in (response.reason or "")
    assert "RuntimeError" in (response.reason or "")
    assert "llm unreachable" in (response.reason or "")


def test_clarify_tool_response_roundtrip() -> None:
    response = ClarifyToolResponse(
        query="sample",
        ok=True,
        need_clarification=False,
        question=None,
        verification="ack",
        mode="fast",
        query_type="literature",
        rubrics=["r1", "r2"],
        channel_priority=["arxiv"],
        channel_skip=[],
    )
    data = response.model_dump()

    assert data["ok"] is True
    assert data["rubrics"] == ["r1", "r2"]
    assert data["channel_skip"] == []
    assert data["reason"] is None


@pytest.mark.asyncio
async def test_run_clarify_tool_call_uses_invoke_clarifier(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirm the registered MCP tool delegates to _invoke_clarifier path."""
    captured: dict = {}

    async def fake_invoke(query, mode_hint, **_kwargs):
        captured["query"] = query
        captured["mode_hint"] = mode_hint
        return ClarifyToolResponse(
            query=query,
            ok=True,
            need_clarification=False,
            verification="stub",
            mode="fast",
        )

    monkeypatch.setattr("autosearch.mcp.server._invoke_clarifier", fake_invoke)

    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager  # noqa: SLF001
    result = await tm.call_tool(
        "run_clarify",
        {"query": "hello world", "mode_hint": "deep"},
    )

    assert isinstance(result, ClarifyToolResponse)
    assert result.verification == "stub"
    assert captured["query"] == "hello world"
    assert captured["mode_hint"] == SearchMode.DEEP
