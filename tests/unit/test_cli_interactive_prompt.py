"""autosearch CLI flag-acceptance regression tests.

These tests confirm that legacy v1 flags (`--interactive`, `--no-interactive`,
`--json`) are still accepted by the v2 query command without raising a Typer
parse error. They do not assert behavior of the underlying pipeline — that's
covered by `test_cli_query.py` and `test_query_pipeline.py` with the orchestrator
stubbed out.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from autosearch.cli.main import app
from autosearch.cli.query_pipeline import QueryResult

runner = CliRunner()


@pytest.fixture(autouse=True)
def stub_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the orchestrator so these tests don't hit network."""

    async def _fake_run_query(query: str, **_kwargs: object) -> QueryResult:
        return QueryResult(query=query, channels_used=["arxiv"], evidence=[])

    monkeypatch.setattr("autosearch.cli.query_pipeline.run_query", _fake_run_query)


def test_interactive_flag_accepted() -> None:
    result = runner.invoke(app, ["query", "test", "--interactive"])
    assert result.exit_code == 0


def test_no_interactive_flag_accepted() -> None:
    result = runner.invoke(app, ["query", "test", "--no-interactive"])
    assert result.exit_code == 0


def test_json_mode_flag_accepted() -> None:
    result = runner.invoke(app, ["query", "test", "--json"])
    assert result.exit_code == 0
