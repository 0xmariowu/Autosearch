# Self-written, plan v2.3 § 7
from typer.testing import CliRunner

from autosearch import __version__
from autosearch.cli.main import app

runner = CliRunner()


def test_version_flag_prints_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
