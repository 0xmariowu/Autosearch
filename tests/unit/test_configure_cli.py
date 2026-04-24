"""Tests for autosearch configure CLI subcommand."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from autosearch.cli.main import app

runner = CliRunner()


def test_configure_non_tty_with_inline_value_succeeds(tmp_path, monkeypatch):
    """Updated for v2: passing the value inline is allowed (it's what install
    scripts do); only "no value AND no --stdin AND not a TTY" is rejected.
    See tests/unit/test_cli_configure.py for the broader contract."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(app, ["configure", "MY_KEY", "myvalue"])
    assert result.exit_code == 0, result.output


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
    content = secrets.read_text(encoding="utf-8")
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
    assert "old" in secrets.read_text(encoding="utf-8")


def test_configure_no_value_no_stdin_in_non_tty_errors(tmp_path, monkeypatch):
    """Replaces the old "abort on no-confirm" test — v2 has no confirmation
    prompt because inline-value/--stdin/hidden-prompt cover the legitimate
    cases. The remaining failure mode is "no value, no --stdin, no TTY"."""
    monkeypatch.setenv("HOME", str(tmp_path))
    with patch("autosearch.cli.main._is_tty", return_value=False):
        result = runner.invoke(app, ["configure", "NEW_KEY"])
    assert result.exit_code != 0
    combined = result.output + (result.stderr or "")
    assert "no value" in combined.lower() or "stdin" in combined.lower()
