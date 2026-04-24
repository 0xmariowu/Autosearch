"""Bug 4 (fix-plan): `autosearch login --stdin` reads the cookie from stdin
so it doesn't leak into shell history / process list. `--from-string` still
works for backward compatibility but emits a deprecation warning."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from autosearch.cli.main import app


@pytest.fixture
def tmp_secrets(tmp_path, monkeypatch):
    secrets_file = tmp_path / "ai-secrets.env"
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(secrets_file))
    yield secrets_file


def test_login_stdin_writes_cookie_without_command_line_leak(tmp_secrets) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["login", "bilibili", "--stdin"],
        input="SESSDATA=xxx; bili_jct=yyy",
    )
    assert result.exit_code == 0, result.output
    assert tmp_secrets.exists()
    body = tmp_secrets.read_text(encoding="utf-8")
    assert "BILIBILI_COOKIES" in body
    assert "SESSDATA=xxx" in body


def test_login_stdin_rejects_empty_input(tmp_secrets) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["login", "bilibili", "--stdin"], input="")
    assert result.exit_code != 0


def test_login_from_string_still_works_with_deprecation_warning(tmp_secrets) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["login", "bilibili", "--from-string", "SESSDATA=zzz"],
    )
    assert result.exit_code == 0, result.output
    assert tmp_secrets.exists()
    body = tmp_secrets.read_text(encoding="utf-8")
    assert "SESSDATA=zzz" in body
    assert "deprecated" in result.output.lower() or "history" in result.output.lower()


def test_login_help_recommends_stdin_over_from_string() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["login", "--help"])
    assert result.exit_code == 0
    assert "--stdin" in result.output
    assert "DEPRECATED" in result.output or "deprecated" in result.output.lower()
