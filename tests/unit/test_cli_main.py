"""autosearch CLI — core behaviour tests after v2 pipeline removal."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from autosearch.cli import main as cli_main

runner = CliRunner()


def test_cli_exits_nonzero_with_deprecation_message() -> None:
    result = runner.invoke(cli_main.app, ["query", "test", "--no-stream"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "deprecated" in combined.lower() or "list_skills" in combined


def test_cli_rejects_empty_query() -> None:
    result = runner.invoke(cli_main.app, ["query", ""])
    assert result.exit_code == 2
    assert result.stderr == "Query must not be empty.\n"


def test_doctor_exits_zero_and_reports_channels() -> None:
    result = runner.invoke(cli_main.app, ["doctor"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    # The human-readable report groups channels by tier; the always-on
    # group ("开箱即用") is always present because free channels exist.
    assert "开箱即用" in result.stdout


def test_doctor_json_flag_emits_valid_json() -> None:
    result = runner.invoke(cli_main.app, ["doctor", "--json"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload, "expected at least one channel in --json output"
    first = payload[0]
    assert {"channel", "status", "tier"} <= set(first)


def test_mcp_check_reports_required_tools() -> None:
    result = runner.invoke(cli_main.app, ["mcp-check"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    for required in cli_main._REQUIRED_MCP_TOOLS:
        assert required in result.stdout, f"{required} missing from mcp-check output"
    assert "OK" in result.stdout


def test_unknown_subcommand_no_longer_silently_routes_to_query() -> None:
    result = runner.invoke(cli_main.app, ["nonexistent-command"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    # After removing the default-query fallback, the deprecation path
    # from `query` must not be triggered for unknown subcommands.
    assert "deprecated" not in combined.lower()


def test_init_dry_run_shows_writes_without_touching_filesystem(tmp_path, monkeypatch) -> None:
    """`init --dry-run` exits 0, prints the planned MCP writes for whichever
    clients are detected, and creates no files. This is the safe path for
    agent-driven installs."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".cursor").mkdir()

    result = runner.invoke(cli_main.app, ["init", "--dry-run"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "Dry-run" in result.stdout
    assert "claude" in result.stdout and "cursor" in result.stdout
    assert not (tmp_path / ".claude" / "mcp.json").exists()
    assert not (tmp_path / ".cursor" / "mcp.json").exists()


def test_mcp_check_with_client_passes_when_writer_was_run(tmp_path, monkeypatch) -> None:
    """End-to-end: write the Claude config via the writer, then `mcp-check
    --client claude` should report the entry as present."""
    from autosearch.cli.mcp_config_writers import ClaudeCodeWriter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    ClaudeCodeWriter().write()

    result = runner.invoke(cli_main.app, ["mcp-check", "--client", "claude"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "Client config check (claude)" in result.stdout
    assert "mcpServers.autosearch" in result.stdout


def test_mcp_check_with_client_fails_when_entry_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    # Write a config that has the WRONG shape (entry at root, like the old bug)
    (tmp_path / ".claude" / "mcp.json").write_text(
        '{"autosearch": {"command": "autosearch-mcp"}}', encoding="utf-8"
    )

    result = runner.invoke(cli_main.app, ["mcp-check", "--client", "claude"])
    assert result.exit_code != 0
    output = result.stdout + (result.stderr or "")
    # Either "missing `mcpServers` object" (when namespace absent) or
    # "missing `mcpServers.autosearch` entry" (when namespace present but no entry)
    # — both prove verify() rejected the broken config.
    assert "mcpServers" in output and "missing" in output


def test_mcp_check_rejects_unknown_client(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(cli_main.app, ["mcp-check", "--client", "vim"])
    assert result.exit_code != 0
    assert "unknown client" in (result.stdout + (result.stderr or "")).lower()
