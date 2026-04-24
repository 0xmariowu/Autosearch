"""G3-T5: CLI configure non-TTY smoke test."""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.smoke.conftest import smoke_env


@pytest.mark.smoke
def test_cli_configure_rejects_no_value_no_stdin_in_non_tty() -> None:
    """v2: configure without an inline value AND without --stdin must reject
    in non-TTY contexts (otherwise it would hang trying to prompt)."""
    result = subprocess.run(
        [sys.executable, "-m", "autosearch.cli.main", "configure", "TEST_KEY"],
        input="",
        capture_output=True,
        text=True,
        env=smoke_env(),
        timeout=10,
    )
    assert result.returncode != 0, "configure should reject when no value path is provided"


@pytest.mark.smoke
def test_cli_configure_inline_value_works_non_interactively(tmp_path) -> None:
    """v2: inline-value form is the supported automation path for install
    scripts; must work without a TTY."""
    env = smoke_env()
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "autosearch.cli.main", "configure", "SMOKE_KEY", "smokeval"],
        input="",
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    secrets = (tmp_path / ".config" / "ai-secrets.env").read_text(encoding="utf-8")
    assert "SMOKE_KEY=" in secrets
