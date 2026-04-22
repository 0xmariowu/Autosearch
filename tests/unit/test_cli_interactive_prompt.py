"""autosearch CLI interactive prompt — v2 deprecation behaviour.

After pipeline removal, the query command exits with a deprecation notice
before reaching scope resolution or interactive prompts.
"""

from __future__ import annotations

from typer.testing import CliRunner

from autosearch.cli.main import app

runner = CliRunner()


def test_interactive_flags_accepted_but_deprecation_exits() -> None:
    result = runner.invoke(app, ["query", "test", "--interactive"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "deprecated" in combined.lower() or "list_skills" in combined


def test_no_interactive_flag_accepted() -> None:
    result = runner.invoke(app, ["query", "test", "--no-interactive"])
    assert result.exit_code != 0


def test_json_mode_flag_accepted() -> None:
    result = runner.invoke(app, ["query", "test", "--json"])
    assert result.exit_code != 0
