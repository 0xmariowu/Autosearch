"""autosearch query CLI — v2 deprecation behaviour.

The legacy pipeline-based ``autosearch query`` command now exits immediately with
a deprecation notice directing users to the v2 MCP tools instead.
"""

from __future__ import annotations

from typer.testing import CliRunner

from autosearch.cli.main import app

runner = CliRunner()


def test_cli_query_exits_nonzero_with_deprecation_message() -> None:
    result = runner.invoke(app, ["query", "test research question"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "deprecated" in combined.lower() or "list_skills" in combined


def test_cli_bare_query_routes_to_query_command() -> None:
    result = runner.invoke(app, ["query", "anything"])
    assert result.exit_code in (1, 2)
