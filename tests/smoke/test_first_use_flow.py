"""P1-7: fresh-install first-use flow smoke test.

A user who runs `pipx install autosearch` and immediately tries
`autosearch query "..."` must not be blocked by missing API keys, missing
network, or pipeline crashes. This test exercises the full CLI → pipeline →
render path under `AUTOSEARCH_LLM_MODE=dummy` so it runs offline and proves
the closed loop: the binary exits 0 and emits a structured brief (or a
deterministic "no evidence" brief when no real channels are reachable).
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from tests.smoke.conftest import console_script_command, smoke_env


@pytest.mark.smoke
def test_query_markdown_loop_exits_zero() -> None:
    """`autosearch query "..."` returns a markdown brief and exits 0 in dummy mode."""
    result = subprocess.run(
        [*console_script_command("autosearch", "autosearch.cli.main"), "query", "smoke test query"],
        capture_output=True,
        text=True,
        env=smoke_env(AUTOSEARCH_LLM_MODE="dummy"),
        timeout=60,
    )

    assert result.returncode == 0, (
        f"query exited {result.returncode}; stderr:\n{result.stderr}\nstdout:\n{result.stdout}"
    )
    assert "Traceback" not in result.stderr, f"unexpected traceback:\n{result.stderr}"

    # Pipeline must produce one of the three documented brief shapes —
    # evidence, no-evidence, or clarification — never an empty stdout.
    out = result.stdout
    assert out.strip(), "expected non-empty markdown brief on stdout"
    assert any(
        marker in out
        for marker in (
            "# AutoSearch evidence brief",
            "# No evidence found",
            "# Clarification needed",
        )
    ), f"output missing expected brief heading; got:\n{out[:500]}"


@pytest.mark.smoke
def test_query_json_loop_emits_valid_envelope() -> None:
    """`autosearch query "..." --json` emits a parseable envelope with the documented fields."""
    result = subprocess.run(
        [
            *console_script_command("autosearch", "autosearch.cli.main"),
            "query",
            "smoke test query",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=smoke_env(AUTOSEARCH_LLM_MODE="dummy"),
        timeout=60,
    )

    assert result.returncode == 0, (
        f"query --json exited {result.returncode}; stderr:\n{result.stderr}\nstdout:\n{result.stdout}"
    )

    payload = json.loads(result.stdout)
    for field in ("query", "channels_used", "evidence_count", "evidence"):
        assert field in payload, f"missing field {field!r} in JSON envelope: {payload}"
    assert payload["query"] == "smoke test query"
    assert isinstance(payload["channels_used"], list)
    assert isinstance(payload["evidence"], list)
    assert payload["evidence_count"] == len(payload["evidence"])


@pytest.mark.smoke
def test_first_use_error_path_redacted(tmp_path) -> None:
    leaked_key = "sk-FAKEKEY" + "1234567890abcdef"
    (tmp_path / "sitecustomize.py").write_text(
        """
import autosearch.cli.query_pipeline as query_pipeline
from autosearch.cli.query_pipeline import QueryResult

_LEAKED_KEY = "sk-FAKEKEY" + "1234567890abcdef"


async def _failing_run_query(_query: str, **_kwargs: object) -> QueryResult:
    raise RuntimeError(f"upstream returned token {_LEAKED_KEY}")


query_pipeline.run_query = _failing_run_query
""",
        encoding="utf-8",
    )
    env = smoke_env(AUTOSEARCH_LLM_MODE="dummy")
    env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{env['PYTHONPATH']}"

    result = subprocess.run(
        [
            *console_script_command("autosearch", "autosearch.cli.main"),
            "query",
            "smoke redaction query",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 1, (
        f"query exited {result.returncode}; stderr:\n{result.stderr}\nstdout:\n{result.stdout}"
    )
    assert leaked_key not in result.stderr
    assert "[REDACTED]" in result.stderr


@pytest.mark.smoke
def test_query_help_lists_subcommand() -> None:
    """`autosearch query --help` proves the v2 thin-orchestration CLI is wired up."""
    result = subprocess.run(
        [*console_script_command("autosearch", "autosearch.cli.main"), "query", "--help"],
        capture_output=True,
        text=True,
        env=smoke_env(),
        timeout=15,
    )

    assert result.returncode == 0, (
        f"query --help exited {result.returncode}; stderr:\n{result.stderr}"
    )
    assert "query" in result.stdout.lower(), f"help missing 'query'; got:\n{result.stdout[:400]}"
