"""G3-T5: CLI configure non-TTY smoke test."""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.smoke.conftest import smoke_env


@pytest.mark.smoke
def test_cli_configure_rejects_non_tty() -> None:
    """autosearch configure must exit non-zero when stdin is not a TTY."""
    result = subprocess.run(
        [sys.executable, "-m", "autosearch.cli.main", "configure", "TEST_KEY", "testvalue"],
        input="",
        capture_output=True,
        text=True,
        env=smoke_env(),
        timeout=10,
    )
    assert result.returncode != 0, "configure should reject non-TTY stdin"
    assert "TTY" in result.stdout + result.stderr, (
        f"Expected 'TTY' error message, got:\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
