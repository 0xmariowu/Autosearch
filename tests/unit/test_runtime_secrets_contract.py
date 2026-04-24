"""End-to-end contract: a key in ~/.config/ai-secrets.env must be visible to
the actual runtime — channel methods, LLM providers, and any code that does
`os.getenv()` — not just to `doctor` and the environment probe.

Plan §P0-1 reproduction: before this contract holds, a user can run
`autosearch configure YOUTUBE_API_KEY xxx`, see `doctor` report `youtube ok`,
and then have the YouTube channel return empty results because `data_api_v3.py`
called `os.environ.get("YOUTUBE_API_KEY")` and got None.
"""

from __future__ import annotations

import os

import pytest

from autosearch.core.secrets_store import inject_into_env


@pytest.fixture
def isolated_secrets_file(tmp_path, monkeypatch):
    """Point AUTOSEARCH_SECRETS_FILE at a controlled tmp file and clear any
    process-env values that might mask file precedence."""
    secrets_file = tmp_path / "ai-secrets.env"
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(secrets_file))
    return secrets_file


def test_inject_pushes_missing_keys_from_file_into_env(isolated_secrets_file, monkeypatch):
    isolated_secrets_file.write_text(
        "RUNTIME_CONTRACT_TEST_KEY=from-file-value\n", encoding="utf-8"
    )
    monkeypatch.delenv("RUNTIME_CONTRACT_TEST_KEY", raising=False)

    injected = inject_into_env()

    assert "RUNTIME_CONTRACT_TEST_KEY" in injected
    assert os.environ.get("RUNTIME_CONTRACT_TEST_KEY") == "from-file-value"


def test_inject_does_not_overwrite_explicit_env(isolated_secrets_file, monkeypatch):
    """Process env always wins — an explicit env override is a deliberate user
    choice and the file must not silently clobber it."""
    isolated_secrets_file.write_text("RUNTIME_CONTRACT_OVERRIDE_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("RUNTIME_CONTRACT_OVERRIDE_KEY", "from-process")

    injected = inject_into_env()

    assert "RUNTIME_CONTRACT_OVERRIDE_KEY" not in injected
    assert os.environ.get("RUNTIME_CONTRACT_OVERRIDE_KEY") == "from-process"


def test_inject_skips_empty_values(isolated_secrets_file, monkeypatch):
    isolated_secrets_file.write_text("RUNTIME_CONTRACT_EMPTY=\n", encoding="utf-8")
    monkeypatch.delenv("RUNTIME_CONTRACT_EMPTY", raising=False)

    injected = inject_into_env()
    assert "RUNTIME_CONTRACT_EMPTY" not in injected


def test_inject_is_idempotent(isolated_secrets_file, monkeypatch):
    isolated_secrets_file.write_text("RUNTIME_CONTRACT_IDEMPOTENT=once\n", encoding="utf-8")
    monkeypatch.delenv("RUNTIME_CONTRACT_IDEMPOTENT", raising=False)

    first = inject_into_env()
    second = inject_into_env()
    assert "RUNTIME_CONTRACT_IDEMPOTENT" in first
    assert "RUNTIME_CONTRACT_IDEMPOTENT" not in second  # already set
    assert os.environ.get("RUNTIME_CONTRACT_IDEMPOTENT") == "once"


def test_mcp_create_server_pushes_secrets_to_env(isolated_secrets_file, monkeypatch):
    """The Plan §P0-1 acceptance: when the MCP server starts, secrets-file
    keys must already be visible to subsequent `os.getenv()` calls."""
    isolated_secrets_file.write_text("MCP_STARTUP_SECRET_TEST=hello-from-file\n", encoding="utf-8")
    monkeypatch.delenv("MCP_STARTUP_SECRET_TEST", raising=False)
    # Force a dummy LLM mode so create_server doesn't try to instantiate a
    # real provider that needs a key we haven't stubbed.
    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")

    from autosearch.mcp.server import create_server

    create_server()
    assert os.environ.get("MCP_STARTUP_SECRET_TEST") == "hello-from-file"


def test_cli_callback_pushes_secrets_to_env(isolated_secrets_file, monkeypatch):
    """The CLI entrypoint must push secrets too — otherwise `autosearch doctor`
    in a new shell where the user just ran `autosearch configure` won't see the
    new key (CLI doesn't go through MCP startup)."""
    isolated_secrets_file.write_text("CLI_STARTUP_SECRET_TEST=from-cli-startup\n", encoding="utf-8")
    monkeypatch.delenv("CLI_STARTUP_SECRET_TEST", raising=False)

    from typer.testing import CliRunner

    from autosearch.cli import main as cli_main

    runner = CliRunner()
    # Any subcommand triggers the callback.
    runner.invoke(cli_main.app, ["doctor", "--json"])

    assert os.environ.get("CLI_STARTUP_SECRET_TEST") == "from-cli-startup"
