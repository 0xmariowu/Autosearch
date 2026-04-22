"""G2-T10: Test ClarifyToolResponse.question_options field (PRE-1/PRE-2)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from autosearch.core.models import ClarifyResult, SearchMode
from autosearch.mcp.server import ClarifyToolResponse


def _make_clarify_result(
    need_clarification: bool, question_options: list[str] | None = None
) -> ClarifyResult:
    return ClarifyResult(
        need_clarification=need_clarification,
        question="Which region?" if need_clarification else None,
        question_options=question_options
        or (["香港区", "国服", "对比"] if need_clarification else []),
        verification=None if need_clarification else "ok",
        rubrics=[],
        mode=SearchMode.FAST,
    )


@pytest.mark.asyncio()
async def test_question_options_populated_when_need_clarification():
    """When need_clarification=true, question_options should be forwarded."""
    from autosearch.mcp.server import _invoke_clarifier

    mock_clarifier = AsyncMock()
    mock_clarifier.clarify.return_value = _make_clarify_result(
        need_clarification=True,
        question_options=["香港区", "国服", "两个都要"],
    )

    response = await _invoke_clarifier(
        query="XGP 怎么买",
        mode_hint=None,
        clarifier=mock_clarifier,
        llm=object(),
        channels=[],
    )

    assert response.ok is True
    assert response.need_clarification is True
    assert response.question_options == ["香港区", "国服", "两个都要"]


@pytest.mark.asyncio()
async def test_question_options_empty_when_no_clarification_needed():
    """When need_clarification=false, question_options should be empty."""
    from autosearch.mcp.server import _invoke_clarifier

    mock_clarifier = AsyncMock()
    mock_clarifier.clarify.return_value = _make_clarify_result(
        need_clarification=False,
        question_options=[],
    )

    response = await _invoke_clarifier(
        query="DuckDB vector search limitations",
        mode_hint=None,
        clarifier=mock_clarifier,
        llm=object(),
        channels=[],
    )

    assert response.ok is True
    assert response.need_clarification is False
    assert response.question_options == []


def test_clarify_tool_response_accepts_question_options():
    """ClarifyToolResponse model accepts question_options field."""
    r = ClarifyToolResponse(
        query="test",
        ok=True,
        need_clarification=True,
        question="Which option?",
        question_options=["A", "B", "C"],
    )
    assert r.question_options == ["A", "B", "C"]
