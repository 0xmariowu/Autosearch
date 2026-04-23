# Self-written, plan v2.3 § 4.5 (autosearch init minimal)
from pathlib import Path

import pytest
from typer.testing import CliRunner

import autosearch.cli.main as cli_main
from autosearch.cli.main import app

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})


def test_cli_init_prints_summary_and_writes_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    providers = {
        "claude_code": True,
        "anthropic": False,
        "openai": True,
        "gemini": False,
    }
    monkeypatch.setattr(cli_main.InitRunner, "detect_providers", lambda self: providers)

    # Set both HOME (Unix) and USERPROFILE (Windows) so Path.home() is redirected on all platforms
    home_env = {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    result = runner.invoke(app, ["init"], env=home_env)

    assert result.exit_code == 0
    # New banner-style output
    assert "AutoSearch" in result.stdout
    assert "You are all set" in result.stdout
    assert "Integration Status" in result.stdout
    for provider in providers:
        assert any(provider in line for line in result.stdout.splitlines())
    assert (tmp_path / ".autosearch" / "config.yaml").exists()
