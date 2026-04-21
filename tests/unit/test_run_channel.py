"""Tests for the run_channel MCP tool — tool-supplier entry for channel execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from autosearch.core.models import Evidence, SubQuery
from autosearch.mcp.server import (
    RunChannelResponse,
    _search_single_channel,
    create_server,
)


class _FakeChannel:
    """Minimal channel stub that satisfies the autosearch Channel protocol."""

    def __init__(self, name: str, results: list[Evidence] | Exception = None):
        self.name = name
        self.languages = ["en"]
        self._results = results if results is not None else []

    async def search(self, query: SubQuery) -> list[Evidence]:
        if isinstance(self._results, Exception):
            raise self._results
        return list(self._results)


def _make_evidence(url: str, title: str, source_channel: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet="snippet text",
        content=None,
        source_channel=source_channel,
        fetched_at=datetime.now(tz=timezone.utc),
        score=0.5,
    )


@pytest.mark.asyncio
async def test_search_single_channel_returns_slim_dicts() -> None:
    channel = _FakeChannel(
        name="bilibili",
        results=[
            _make_evidence("https://example.com/1", "Title one", "bilibili"),
            _make_evidence("https://example.com/2", "Title two", "bilibili"),
        ],
    )

    slim = await _search_single_channel(channel, query="test", rationale="why")

    assert len(slim) == 2
    assert slim[0]["url"] == "https://example.com/1"
    assert slim[0]["title"] == "Title one"
    assert "source_page" in slim[0]  # Evidence.to_slim_dict includes the field (None when absent)


@pytest.mark.asyncio
async def test_search_single_channel_propagates_exception() -> None:
    channel = _FakeChannel(name="broken", results=RuntimeError("upstream down"))

    with pytest.raises(RuntimeError, match="upstream down"):
        await _search_single_channel(channel, query="test", rationale="")


@pytest.mark.asyncio
async def test_run_channel_tool_is_registered() -> None:
    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tools = await server.list_tools()
    tool_names = {tool.name for tool in tools}
    assert "run_channel" in tool_names


@pytest.mark.asyncio
async def test_run_channel_unknown_channel_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_channels = [_FakeChannel(name="bilibili"), _FakeChannel(name="arxiv")]
    monkeypatch.setattr("autosearch.mcp.server._build_channels", lambda: fake_channels)

    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tools = await server.list_tools()
    run_channel_tool = next(t for t in tools if t.name == "run_channel")
    assert run_channel_tool is not None

    # Invoke via FastMCP's internal tool manager — it returns the pydantic
    # model directly when the tool's return type is a BaseModel.
    tm = server._tool_manager  # noqa: SLF001 — test-only access
    response = await tm.call_tool(
        "run_channel",
        {"channel_name": "does_not_exist", "query": "hello"},
    )
    assert isinstance(response, RunChannelResponse)
    assert response.ok is False
    assert response.channel == "does_not_exist"
    assert "unknown_channel" in (response.reason or "")
    assert "bilibili" in (response.reason or "")
    assert "arxiv" in (response.reason or "")


@pytest.mark.asyncio
async def test_run_channel_happy_path_returns_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_channels = [
        _FakeChannel(
            name="bilibili",
            results=[
                _make_evidence("https://example.com/a", "Item A", "bilibili"),
                _make_evidence("https://example.com/b", "Item B", "bilibili"),
                _make_evidence("https://example.com/c", "Item C", "bilibili"),
            ],
        ),
    ]
    monkeypatch.setattr("autosearch.mcp.server._build_channels", lambda: fake_channels)

    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager  # noqa: SLF001
    response = await tm.call_tool(
        "run_channel",
        {"channel_name": "bilibili", "query": "test query", "k": 2},
    )

    assert isinstance(response, RunChannelResponse)
    assert response.ok is True
    assert response.channel == "bilibili"
    assert response.count_total == 3
    assert response.count_returned == 2
    assert len(response.evidence) == 2
    assert response.evidence[0]["url"] == "https://example.com/a"


@pytest.mark.asyncio
async def test_run_channel_search_exception_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_channels = [_FakeChannel(name="flaky", results=RuntimeError("net down"))]
    monkeypatch.setattr("autosearch.mcp.server._build_channels", lambda: fake_channels)

    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    tm = server._tool_manager  # noqa: SLF001
    response = await tm.call_tool(
        "run_channel",
        {"channel_name": "flaky", "query": "test"},
    )

    assert isinstance(response, RunChannelResponse)
    assert response.ok is False
    assert response.channel == "flaky"
    assert "channel_error" in (response.reason or "")
    assert "RuntimeError" in (response.reason or "")
    assert "net down" in (response.reason or "")


def test_run_channel_response_model_roundtrip() -> None:
    response = RunChannelResponse(
        channel="bilibili",
        ok=True,
        evidence=[{"url": "x", "title": "y"}],
        count_total=1,
        count_returned=1,
    )
    data: Any = response.model_dump()
    assert data["ok"] is True
    assert data["evidence"][0]["url"] == "x"
    assert data["count_returned"] == 1
    assert data["reason"] is None
