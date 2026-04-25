"""Tests for autosearch.core.delegate."""

from __future__ import annotations


import pytest

from autosearch.channels.base import (
    BudgetExhausted,
    ChannelAuthError,
    MethodUnavailable,
    RateLimited,
)
from autosearch.core.delegate import run_subtask


async def _fake_search(name: str, results: list[dict], fail: bool = False):
    async def _fn(channel_name: str) -> list[dict]:
        if fail:
            raise RuntimeError(f"channel {channel_name} failed")
        return results

    return _fn


@pytest.mark.asyncio
async def test_parallel_returns_evidence_from_all_channels():
    async def _search(channel_name: str) -> list[dict]:
        return [{"url": f"https://{channel_name}.com/1", "title": "t"}]

    result = await run_subtask("task", ["ch_a", "ch_b"], "query", _search_fn=_search)
    assert "ch_a" in result.evidence_by_channel
    assert "ch_b" in result.evidence_by_channel
    assert result.failed_channels == []


@pytest.mark.asyncio
async def test_failed_channel_recorded_not_raised():
    async def _search(channel_name: str) -> list[dict]:
        if channel_name == "bad":
            raise RuntimeError("boom")
        return [{"url": "https://ok.com"}]

    result = await run_subtask("task", ["ok", "bad"], "query", _search_fn=_search)
    assert "ok" in result.evidence_by_channel
    assert "bad" in result.failed_channels
    assert "bad" not in result.evidence_by_channel
    assert result.failed_channel_details[0]["channel"] == "bad"
    assert result.failed_channel_details[0]["status"] == "channel_error"


@pytest.mark.asyncio
async def test_max_per_channel_limits_evidence():
    async def _search(channel_name: str) -> list[dict]:
        return [{"url": f"https://x.com/{i}"} for i in range(20)]

    result = await run_subtask("task", ["ch"], "query", max_per_channel=3, _search_fn=_search)
    assert len(result.evidence_by_channel["ch"]) <= 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (ChannelAuthError("HTTP 403"), "auth_failed"),
        (RateLimited("HTTP 429"), "rate_limited"),
        (BudgetExhausted("wallet empty"), "budget_exhausted"),
        (MethodUnavailable("missing config: TOKEN required"), "not_configured"),
        (MethodUnavailable("exhausted all fallback methods"), "channel_unavailable"),
    ],
)
async def test_failed_channel_details_preserve_typed_statuses(
    exc: Exception,
    expected_status: str,
) -> None:
    async def _search(_channel_name: str) -> list[dict]:
        raise exc

    result = await run_subtask("task", ["bad"], "query", _search_fn=_search)

    assert result.failed_channels == ["bad"]
    assert result.failed_channel_details[0]["channel"] == "bad"
    assert result.failed_channel_details[0]["status"] == expected_status
    assert result.failed_channel_details[0]["reason"]
    assert "fix_hint" in result.failed_channel_details[0]
    if expected_status == "auth_failed":
        assert result.failed_channel_details[0]["fix_hint"]


@pytest.mark.asyncio
async def test_delegate_subtask_mcp_response_includes_failed_channel_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autosearch.core.delegate import SubtaskResult
    from autosearch.mcp.server import create_server

    async def _fake_run_subtask(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return SubtaskResult(
            failed_channels=["bad"],
            failed_channel_details=[
                {
                    "channel": "bad",
                    "status": "auth_failed",
                    "reason": "auth_failed: ChannelAuthError: HTTP 403",
                    "fix_hint": "Refresh the channel login or configure a valid API key.",
                    "unmet_requires": [],
                }
            ],
        )

    monkeypatch.setattr("autosearch.core.delegate.run_subtask", _fake_run_subtask)
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]

    payload = await server._tool_manager.call_tool(  # noqa: SLF001
        "delegate_subtask",
        {"task_description": "task", "channels": ["bad"], "query": "query"},
    )

    assert payload["failed_channels"] == ["bad"]
    assert payload["failed_channel_details"][0]["status"] == "auth_failed"
