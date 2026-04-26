from __future__ import annotations

from typing import Any

import pytest

from autosearch.core import delegate as delegate_module
from autosearch.core.channel_runtime import get_channel_runtime
from autosearch.mcp.server import create_server


@pytest.mark.asyncio
async def test_delegate_subtask_passes_shared_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MCP delegate_subtask tool must call run_subtask with the same
    runtime that get_channel_runtime() returns — otherwise the rate
    limiter and cost tracker do not accumulate across delegate calls."""
    captured: dict[str, Any] = {}

    async def _fake_run_subtask(
        task_description: str,
        channels: list[str],
        query: str,
        max_per_channel: int = 5,
        *,
        channel_runtime: Any,
        **kwargs: Any,
    ) -> delegate_module.SubtaskResult:
        captured["channel_runtime"] = channel_runtime
        captured["channels"] = channels
        return delegate_module.SubtaskResult()

    monkeypatch.setattr(delegate_module, "run_subtask", _fake_run_subtask)

    server = create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    await server._tool_manager.call_tool(
        "delegate_subtask",
        {
            "task_description": "task",
            "channels": ["alpha"],
            "query": "q",
        },
    )

    assert captured["channel_runtime"] is get_channel_runtime()
    assert captured["channels"] == ["alpha"]
