"""autosearch CLI — core behaviour tests after v2 pipeline removal."""

from __future__ import annotations

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
