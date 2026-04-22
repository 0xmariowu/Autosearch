# Self-written, plan v2.3 § W2 smoke MCP stdio
import json
import subprocess

import pytest

from tests.smoke.conftest import (
    console_script_command,
    read_jsonrpc_message,
    smoke_env,
    stop_process,
)


def _send_jsonrpc(process: subprocess.Popen[str], payload: dict[str, object]) -> None:
    if process.stdin is None:
        raise AssertionError("Process stdin is not available.")
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()


@pytest.mark.slow
@pytest.mark.smoke
def test_mcp_stdio_smoke() -> None:
    process = subprocess.Popen(
        [*console_script_command("autosearch-mcp", "autosearch.mcp.cli")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=smoke_env(AUTOSEARCH_LLM_MODE="dummy"),
    )

    try:
        _send_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.0.0"},
                },
            },
        )
        initialize_response = read_jsonrpc_message(process, timeout=5.0)

        assert initialize_response["jsonrpc"] == "2.0"
        assert "result" in initialize_response

        _send_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        _send_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        tools_response = read_jsonrpc_message(process, timeout=5.0)

        assert tools_response["jsonrpc"] == "2.0"
        tool_names = {tool["name"] for tool in tools_response["result"]["tools"]}
        assert {"research", "health"} <= tool_names
        # Core v2 tools must be registered
        assert "list_skills" in tool_names
        assert "doctor" in tool_names
        assert "list_channels" in tool_names

        if process.stdin is not None:
            process.stdin.close()
    finally:
        stop_process(process)


@pytest.mark.smoke
def test_mcp_tools_registered_via_python() -> None:
    """G3-T1/T2/T3: Verify tool registration and responses via Python import.

    Uses Python import instead of stdio to avoid structlog stdout contamination
    in the JSON-RPC read loop when tool calls trigger skill scanning.
    """
    import os

    os.environ["AUTOSEARCH_LLM_MODE"] = "dummy"
    try:
        from autosearch.mcp.server import create_server

        server = create_server()
        tool_names = {t.name for t in server._tool_manager.list_tools()}

        required = {
            "list_skills",
            "doctor",
            "list_channels",
            "run_clarify",
            "run_channel",
            "loop_init",
            "citation_create",
            "select_channels_tool",
        }
        missing = required - tool_names
        assert not missing, f"Missing tools: {missing}"

        # G3-T2: doctor() returns list of channel status dicts
        result = server._tool_manager._tools["doctor"].fn()
        assert isinstance(result, list)
        assert len(result) >= 1
        assert all("channel" in item and "status" in item for item in result)

        # G3-T1: list_skills returns >= 34 channel skills
        ls = server._tool_manager._tools["list_skills"].fn(group="channels")
        assert ls.total >= 34, f"Expected >= 34 channels, got {ls.total}"

        # G3-T3: list_channels returns structured response
        lc = server._tool_manager._tools["list_channels"].fn()
        assert "total" in lc and "channels" in lc
        assert lc["total"] >= 1

    finally:
        os.environ.pop("AUTOSEARCH_LLM_MODE", None)
