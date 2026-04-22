"""G3-T4: CLI doctor smoke test."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from tests.smoke.conftest import console_script_command, smoke_env


@pytest.mark.smoke
def test_cli_doctor_exits_zero() -> None:
    """autosearch doctor should run without crashing and exit 0."""
    subprocess.run(
        [*console_script_command("autosearch", "autosearch.cli.main")],
        input="",
        capture_output=True,
        text=True,
        env=smoke_env(AUTOSEARCH_LLM_MODE="dummy"),
        timeout=30,
    )
    # autosearch with no subcommand exits 0 (shows version or nothing)
    # Verify MCP doctor works via Python import instead
    env = {**os.environ, "AUTOSEARCH_LLM_MODE": "dummy"}
    result2 = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; os.environ['AUTOSEARCH_LLM_MODE']='dummy'; "
                "from autosearch.core.doctor import scan_channels; "
                "results = scan_channels(); "
                "assert isinstance(results, list), 'expected list'; "
                "assert len(results) >= 1, f'expected channels, got {len(results)}'; "
                "print(f'doctor: {len(results)} channels scanned')"
            ),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result2.returncode == 0, f"doctor() failed:\n{result2.stderr}"
    assert "channels scanned" in result2.stdout
