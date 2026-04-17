# Self-written, plan v2.3 § W2 smoke CLI version
import subprocess

import pytest

from autosearch import __version__
from tests.smoke.conftest import console_script_command, smoke_env


@pytest.mark.slow
@pytest.mark.smoke
def test_cli_version_smoke() -> None:
    result = subprocess.run(
        [*console_script_command("autosearch", "autosearch.cli.main"), "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=smoke_env(),
    )

    assert result.returncode == 0, result.stderr
    assert __version__ in result.stdout
