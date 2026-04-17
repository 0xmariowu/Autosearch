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
        if process.stdin is not None:
            process.stdin.close()
    finally:
        stop_process(process)
