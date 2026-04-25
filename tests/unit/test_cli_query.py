"""autosearch query CLI — v2 P1-7 thin orchestration behaviour.

The CLI runs `run_clarify` → top-N `run_channel` calls → renders evidence.
No LLM synthesis happens; the user pastes the brief into a runtime AI.

Tests stub the orchestrator so they run without network access.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from autosearch.cli import main as cli_main
from autosearch.cli.main import app
from autosearch.cli.query_pipeline import QueryResult

runner = CliRunner()


@pytest.fixture
def stub_pipeline(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    async def _fake_run_query(query: str, **kwargs: object) -> QueryResult:
        captured["query"] = query
        captured["kwargs"] = kwargs
        return QueryResult(
            query=query,
            channels_used=["arxiv"],
            evidence=[
                {
                    "url": "https://arxiv.org/abs/2026.0001",
                    "title": "Stub paper",
                    "snippet": "stub snippet",
                    "source_channel": "arxiv",
                }
            ],
        )

    monkeypatch.setattr("autosearch.cli.query_pipeline.run_query", _fake_run_query)
    return captured


def test_cli_query_renders_markdown_brief(stub_pipeline: dict[str, object]) -> None:
    result = runner.invoke(app, ["query", "transformers 2026"])
    assert result.exit_code == 0
    assert "AutoSearch evidence brief" in result.stdout
    assert "Stub paper" in result.stdout
    assert "## Citations" in result.stdout
    assert "Paste the brief above" in result.stdout


def test_cli_query_json_emits_valid_envelope(stub_pipeline: dict[str, object]) -> None:
    result = runner.invoke(app, ["query", "transformers 2026", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["query"] == "transformers 2026"
    assert payload["channels_used"] == ["arxiv"]
    assert payload["evidence_count"] == 1
    assert payload["evidence"][0]["title"] == "Stub paper"


def test_cli_query_rejects_empty_query() -> None:
    result = runner.invoke(app, ["query", "   "])
    assert result.exit_code == 2  # argparse-style usage error
    combined = (result.output or "") + (result.stderr or "")
    assert "Query must not be empty" in combined or "must not be empty" in combined


def test_cli_query_pipeline_failure_surfaces_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _failing(_query: str, **_kwargs: object) -> QueryResult:
        raise RuntimeError("boom")

    monkeypatch.setattr("autosearch.cli.query_pipeline.run_query", _failing)
    result = runner.invoke(app, ["query", "anything", "--json"])
    assert result.exit_code == 1
    combined = (result.output or "") + (result.stderr or "")
    assert "boom" in combined or "RuntimeError" in combined or "query pipeline failed" in combined


def test_cli_query_top_k_passed_through(stub_pipeline: dict[str, object]) -> None:
    result = runner.invoke(app, ["query", "x", "--top-k", "12"])
    assert result.exit_code == 0
    kwargs = stub_pipeline["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["per_channel_k"] == 12


def test_cli_module_main_attribute_present() -> None:
    # Sanity: the module still exposes `app` for the entry point.
    assert hasattr(cli_main, "app")
