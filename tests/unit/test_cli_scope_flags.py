"""autosearch CLI scope flags — Typer parse behaviour for v2 query command.

The v2 thin-orchestration `query` command keeps backward-compat flag surface
(`--depth`, `--channel-scope`, `--no-interactive`, etc.). These tests confirm
Typer still parses or rejects the flag values correctly, with the orchestrator
stubbed so no network is hit.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from autosearch.cli.main import app
from autosearch.cli.query_pipeline import QueryResult

runner = CliRunner()


@pytest.fixture(autouse=True)
def stub_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_run_query(query: str, **_kwargs: object) -> QueryResult:
        return QueryResult(query=query, channels_used=["arxiv"], evidence=[])

    monkeypatch.setattr("autosearch.cli.query_pipeline.run_query", _fake_run_query)


def test_query_invalid_depth_is_bad_parameter() -> None:
    result = runner.invoke(app, ["query", "test", "--depth", "bogus"])
    assert result.exit_code == 2
    assert "Error" in result.stderr


def test_invalid_channel_scope_rejected() -> None:
    result = runner.invoke(app, ["query", "test", "--channel-scope", "invalid"])
    assert result.exit_code == 2


def test_query_with_valid_flags_runs_pipeline() -> None:
    result = runner.invoke(
        app,
        ["query", "test", "--depth", "deep", "--channel-scope", "zh_only", "--no-interactive"],
    )
    assert result.exit_code == 0
