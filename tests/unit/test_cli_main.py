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
