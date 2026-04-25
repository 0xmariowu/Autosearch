# Self-written, plan v2.3 § W2 smoke MCP stdio stdout purity
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.smoke.conftest import console_script_command, smoke_env


def _send_jsonrpc(process: subprocess.Popen[str], payload: dict[str, object]) -> None:
    if process.stdin is None:
        raise AssertionError("Process stdin is not available.")
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()


@pytest.mark.smoke
def test_mcp_stdio_logs_go_to_stderr_not_stdout(tmp_path: Path) -> None:
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    (shim_dir / "sitecustomize.py").write_text(
        "\n".join(
            [
                "import structlog",
                "from autosearch.mcp import server as mcp_server",
                "",
                "_original = mcp_server._search_single_channel",
                "",
                "async def _wrapped(channel, query, rationale):",
                "    structlog.get_logger('tests.smoke').warning(",
                "        'forced_stdio_warning',",
                "        channel=getattr(channel, 'name', 'unknown'),",
                "    )",
                "    return await _original(channel, query, rationale)",
                "",
                "mcp_server._search_single_channel = _wrapped",
                "",
            ]
        ),
        encoding="utf-8",
    )

    env = smoke_env(AUTOSEARCH_LLM_MODE="dummy")
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{shim_dir}{os.pathsep}{pythonpath}" if pythonpath else str(shim_dir)

    process = subprocess.Popen(
        [*console_script_command("autosearch-mcp", "autosearch.mcp.cli")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
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
                "method": "tools/call",
                "params": {
                    "name": "run_channel",
                    "arguments": {
                        "channel_name": "demo",
                        "query": "stdout pollution regression",
                    },
                },
            },
        )
        if process.stdin is not None:
            process.stdin.close()
            process.stdin = None

        stdout, stderr = process.communicate(timeout=20)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()

    assert process.returncode == 0, stderr
    stdout_lines = [line for line in stdout.splitlines() if line.strip()]
    assert stdout_lines, "Expected JSON-RPC output on stdout."

    response_ids: set[int] = set()
    for line in stdout_lines:
        payload = json.loads(line)
        assert isinstance(payload, dict)
        assert payload.get("jsonrpc") == "2.0"
        if isinstance(payload.get("id"), int):
            response_ids.add(payload["id"])

    assert response_ids == {1, 2}
    assert stderr.strip(), "Expected log or diagnostic output on stderr."
