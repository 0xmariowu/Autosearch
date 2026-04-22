"""Tests for autosearch configure CLI subcommand."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from autosearch.cli.main import app

runner = CliRunner()


def test_configure_non_tty_rejected():
    result = runner.invoke(app, ["configure", "MY_KEY", "myvalue"])
    assert result.exit_code == 1
    assert "TTY" in result.output


def _tty_mock():
    """Return a mock stdin that reports as TTY."""
    from unittest.mock import MagicMock

    m = MagicMock()
    m.isatty.return_value = True
    return m


def test_configure_writes_new_key(tmp_path):
    secrets = tmp_path / ".config" / "ai-secrets.env"

    with (
        patch("autosearch.cli.main._is_tty", return_value=True),
        patch("pathlib.Path.home", return_value=tmp_path),
        patch("typer.confirm", return_value=True),
    ):
        result = runner.invoke(app, ["configure", "NEW_KEY", "abc123"])

    assert result.exit_code == 0
    content = secrets.read_text()
    assert "NEW_KEY=" in content


def test_configure_skips_existing_key(tmp_path):
    secrets = tmp_path / ".config" / "ai-secrets.env"
    secrets.parent.mkdir(parents=True)
    secrets.write_text("EXISTING_KEY=old\n")

    with (
        patch("autosearch.cli.main._is_tty", return_value=True),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["configure", "EXISTING_KEY", "newval"])

    assert result.exit_code == 0
    assert "already exists" in result.output
    assert "old" in secrets.read_text()


def test_configure_aborted_on_no_confirm(tmp_path):
    with (
        patch("autosearch.cli.main._is_tty", return_value=True),
        patch("pathlib.Path.home", return_value=tmp_path),
        patch("typer.confirm", return_value=False),
    ):
        result = runner.invoke(app, ["configure", "NEW_KEY", "val"])

    assert result.exit_code == 0
    assert "Aborted" in result.output
    secrets = tmp_path / ".config" / "ai-secrets.env"
    assert not secrets.exists()
