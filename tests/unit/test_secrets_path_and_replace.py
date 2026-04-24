"""Bugs 2/3/4 (fix-plan): secrets-file write target + force-replace + chmod.

- Bug 3: `autosearch configure` and `autosearch login` must write to
  `secrets_path()` (which respects AUTOSEARCH_SECRETS_FILE), not the
  hardcoded `~/.config/ai-secrets.env`.
- Bug 2: `inject_into_env(force=True)` must overwrite an env value previously
  injected from the same file, so `configure --replace` actually reaches the
  long-running MCP runtime.
- Bug 4: cookie writer must chmod the secrets file 0o600 so cookies aren't
  world-readable on shared boxes.
"""

from __future__ import annotations

import os
import stat

import pytest
from typer.testing import CliRunner

from autosearch.cli.main import _write_cookie_to_secrets, app
from autosearch.core import secrets_store


@pytest.fixture
def tmp_secrets(tmp_path, monkeypatch):
    secrets_file = tmp_path / "ai-secrets.env"
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(secrets_file))
    yield secrets_file


def test_configure_writes_to_AUTOSEARCH_SECRETS_FILE(tmp_secrets) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["configure", "YOUTUBE_API_KEY", "test-value"])
    assert result.exit_code == 0, result.output
    assert tmp_secrets.exists(), f"configure must write to {tmp_secrets}, but file is missing"
    body = tmp_secrets.read_text(encoding="utf-8")
    assert "YOUTUBE_API_KEY" in body
    assert "test-value" in body


def test_cookie_writer_writes_to_AUTOSEARCH_SECRETS_FILE(tmp_secrets) -> None:
    _write_cookie_to_secrets("XHS_COOKIES", "a=b; c=d", "xhs", n_cookies=2)
    assert tmp_secrets.exists()
    body = tmp_secrets.read_text(encoding="utf-8")
    assert "XHS_COOKIES" in body


def test_cookie_writer_chmods_secrets_file_to_0600(tmp_secrets) -> None:
    _write_cookie_to_secrets("XHS_COOKIES", "a=b", "xhs")
    assert tmp_secrets.exists()
    mode = stat.S_IMODE(tmp_secrets.stat().st_mode)
    assert mode == 0o600, (
        f"cookie writer must chmod the secrets file 0o600 to keep cookies "
        f"private on shared boxes; got {oct(mode)}"
    )


def test_inject_into_env_default_does_not_overwrite_user_env(tmp_secrets, monkeypatch) -> None:
    tmp_secrets.write_text("YOUTUBE_API_KEY=file-value\n", encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_API_KEY", "user-explicit-value")
    secrets_store.inject_into_env()
    assert os.environ["YOUTUBE_API_KEY"] == "user-explicit-value", (
        "default mode must respect the user's explicit env override"
    )


def test_inject_into_env_force_overwrites_previously_injected_value(
    tmp_secrets, monkeypatch
) -> None:
    """The configure --replace flow: file value changes, env was previously
    injected from an earlier file value. force=True must propagate."""
    tmp_secrets.write_text("YOUTUBE_API_KEY=old-value\n", encoding="utf-8")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    secrets_store.inject_into_env()
    assert os.environ.get("YOUTUBE_API_KEY") == "old-value"

    # Simulate: autosearch configure --replace YOUTUBE_API_KEY new-value
    tmp_secrets.write_text("YOUTUBE_API_KEY=new-value\n", encoding="utf-8")
    secrets_store.inject_into_env(force=True)
    assert os.environ["YOUTUBE_API_KEY"] == "new-value", (
        "force=True must replace the stale env value (Bug 2 / fix-plan)"
    )
