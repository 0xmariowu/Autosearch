# Self-written, plan v2.3 § W2 smoke CLI query
import subprocess

import pytest

from tests.smoke.conftest import console_script_command, smoke_env


@pytest.mark.slow
@pytest.mark.smoke
def test_cli_query_smoke() -> None:
    result = subprocess.run(
        [
            *console_script_command("autosearch", "autosearch.cli.main"),
            "query",
            "test query",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=smoke_env(AUTOSEARCH_LLM_MODE="dummy"),
    )

    assert result.returncode == 0, result.stderr
    assert "## References" in result.stdout or bool(result.stdout.strip())
