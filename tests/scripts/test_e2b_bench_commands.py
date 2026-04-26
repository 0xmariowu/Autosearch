from __future__ import annotations

import importlib
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

# These tests assert that bench-command builders correctly escape shell
# metacharacters when the resulting string is fed to a POSIX shell — the same
# environment the e2b Linux sandbox uses in production. On Windows pytest
# runners (Cross-Platform Tests workflow) the command relies on `$HOME` and
# `.venv/bin/python` syntax that cmd.exe does not understand, so the tests
# fail for environment reasons unrelated to the quoting behavior under test.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="bench commands target POSIX shell (e2b Linux sandbox); cmd.exe cannot run them",
)


def _install_fake_e2b_module(monkeypatch) -> None:
    fake = types.ModuleType("e2b_code_interpreter")
    fake.Sandbox = object
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", fake)


def _make_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "work" / "autosearch"
    python_dir = root / ".venv" / "bin"
    bench_dir = root / "tests" / "e2b" / "bench"
    python_dir.mkdir(parents=True)
    bench_dir.mkdir(parents=True)
    (python_dir / "python").symlink_to(sys.executable)
    (bench_dir / "single_channel_bench.py").write_text("", encoding="utf-8")
    autosearch = python_dir / "autosearch"
    autosearch.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    autosearch.chmod(0o755)
    return root


def test_channel_bench_command_quotes_malicious_channel(monkeypatch, tmp_path) -> None:
    _install_fake_e2b_module(monkeypatch)
    bench_channels = importlib.import_module("scripts.e2b.bench_channels")
    _make_workspace(tmp_path)

    cmd = bench_channels.build_single_channel_bench_command(
        "my-chan; echo PWNED",
        "plain query",
        "fast",
    )
    result = subprocess.run(
        cmd,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
    )

    assert result.returncode == 0
    assert "PWNED" not in result.stdout
    assert "PWNED" not in result.stderr


def test_variance_bench_command_quotes_malicious_query(monkeypatch, tmp_path) -> None:
    _install_fake_e2b_module(monkeypatch)
    bench_variance = importlib.import_module("scripts.e2b.bench_variance")
    _make_workspace(tmp_path)

    cmd = bench_variance.build_autosearch_query_command("query; echo PWNED", "fast")
    result = subprocess.run(
        cmd,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
    )

    assert result.returncode == 0
    assert "PWNED" not in result.stdout
    assert "PWNED" not in result.stderr
