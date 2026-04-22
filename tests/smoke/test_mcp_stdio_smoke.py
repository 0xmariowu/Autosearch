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
        # G3-T1: list_skills, doctor, list_channels must be registered
        assert "list_skills" in tool_names
        assert "doctor" in tool_names
        assert "list_channels" in tool_names

        # G3-T1: list_skills call returns channels
        _send_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_skills", "arguments": {"group": "channels"}},
            },
        )
        list_skills_resp = read_jsonrpc_message(process, timeout=10.0)
        assert "result" in list_skills_resp
        ls_content = list_skills_resp["result"]["content"][0]["text"]
        ls_data = json.loads(ls_content)
        assert ls_data["total"] >= 34, f"Expected >= 34 channel skills, got {ls_data['total']}"

        # G3-T2: doctor() call returns list of channel statuses
        _send_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "doctor", "arguments": {}},
            },
        )
        doctor_resp = read_jsonrpc_message(process, timeout=10.0)
        assert "result" in doctor_resp
        doc_data = json.loads(doctor_resp["result"]["content"][0]["text"])
        assert isinstance(doc_data, list)
        assert len(doc_data) >= 1
        assert all("channel" in item and "status" in item for item in doc_data)

        # G3-T3: list_channels() returns structured response with counts
        _send_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "list_channels", "arguments": {}},
            },
        )
        lc_resp = read_jsonrpc_message(process, timeout=10.0)
        assert "result" in lc_resp
        lc_data = json.loads(lc_resp["result"]["content"][0]["text"])
        assert "total" in lc_data
        assert "ok_count" in lc_data
        assert "channels" in lc_data
        assert lc_data["total"] >= 1

        if process.stdin is not None:
            process.stdin.close()
    finally:
        stop_process(process)
