# Self-written, plan v2.3 § 13.5 Presentation
from unittest.mock import Mock

from typer.testing import CliRunner

import autosearch.cli.main as cli_main

runner = CliRunner()


def test_cli_serve_help_shows_host_and_port_flags() -> None:
    result = runner.invoke(cli_main.app, ["serve", "--help"], env={"NO_COLOR": "1", "TERM": "dumb"})

    assert result.exit_code == 0
    assert "--host" in result.stdout
    assert "--port" in result.stdout


def test_cli_serve_invokes_uvicorn_with_host_and_port(monkeypatch) -> None:
    run_mock = Mock()
    monkeypatch.setattr(cli_main.uvicorn, "run", run_mock)

    result = runner.invoke(
        cli_main.app,
        ["serve", "--host", "127.0.0.1", "--port", "9090"],
    )

    assert result.exit_code == 0
    run_mock.assert_called_once_with(
        "autosearch.server.main:app",
        host="127.0.0.1",
        port=9090,
    )
