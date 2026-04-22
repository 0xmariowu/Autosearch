"""autosearch CLI scope flags — v2 deprecation behaviour.

After pipeline removal, ``autosearch query`` exits with a deprecation notice
before scope resolution. Flag validation (typer) still happens before that.
"""

from __future__ import annotations

from typer.testing import CliRunner

from autosearch.cli.main import app

runner = CliRunner()


def test_query_invalid_depth_is_bad_parameter() -> None:
    result = runner.invoke(app, ["query", "test", "--depth", "bogus"])
    assert result.exit_code == 2
    assert "Error" in result.stderr


def test_invalid_channel_scope_rejected() -> None:
    result = runner.invoke(app, ["query", "test", "--channel-scope", "invalid"])
    assert result.exit_code == 2


def test_query_with_any_valid_flags_exits_deprecation() -> None:
    # Valid flags parse correctly; deprecation exit fires before pipeline is reached.
    result = runner.invoke(
        app,
        ["query", "test", "--depth", "deep", "--channel-scope", "zh_only", "--no-interactive"],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "deprecated" in combined.lower() or "list_skills" in combined
