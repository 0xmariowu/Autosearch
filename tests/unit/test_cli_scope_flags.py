# Self-written for F102 CLI scope flags
import json

import click.testing
from typer.testing import CliRunner

from autosearch.cli.main import app
from autosearch.core.models import (
    ClarifyResult,
    EvaluationResult,
    GradeOutcome,
    SearchMode,
)
from autosearch.core.pipeline import PipelineResult
from autosearch.core.search_scope import SearchScope

runner = CliRunner()


def _ok_result(markdown: str = "# Test\n\nBody") -> PipelineResult:
    return PipelineResult(
        status="ok",
        clarification=ClarifyResult(
            need_clarification=False,
            question=None,
            verification="Enough information to proceed.",
            rubrics=[],
            mode=SearchMode.FAST,
        ),
        markdown=markdown,
        quality=EvaluationResult(
            grade=GradeOutcome.PASS,
            follow_up_gaps=[],
        ),
        iterations=2,
    )


def _install_cli_spy(monkeypatch, pipeline_result: PipelineResult) -> list[dict[str, object]]:
    import autosearch.cli.main as cli_main

    calls: list[dict[str, object]] = []

    class StubPipeline:
        def __init__(self, llm, channels, top_k_evidence: int, on_event=None) -> None:
            self.llm = llm
            self.channels = channels
            self.top_k_evidence = top_k_evidence
            self.on_event = on_event

        async def run(
            self,
            query: str,
            mode_hint: SearchMode | None = None,
            *,
            scope: SearchScope | None = None,
        ) -> PipelineResult:
            calls.append(
                {
                    "query": query,
                    "mode_hint": mode_hint,
                    "top_k_evidence": self.top_k_evidence,
                    "scope": scope,
                }
            )
            return pipeline_result

    monkeypatch.setattr(cli_main, "Pipeline", StubPipeline)
    monkeypatch.setattr(cli_main, "LLMClient", lambda: object())
    monkeypatch.setattr(cli_main, "_build_channels", lambda: [object()])

    return calls


def _set_tty(monkeypatch, value: bool) -> None:
    monkeypatch.setattr(click.testing._NamedTextIOWrapper, "isatty", lambda self: value)


def test_query_accepts_all_new_flags_noninteractive(monkeypatch) -> None:
    calls = _install_cli_spy(monkeypatch, _ok_result())

    result = runner.invoke(
        app,
        [
            "query",
            "test",
            "--languages",
            "MIXED",
            "--depth",
            "DEEP",
            "--format",
            "HTML",
            "--no-interactive",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        {
            "query": "test",
            "mode_hint": SearchMode.DEEP,
            "top_k_evidence": 20,
            "scope": SearchScope(
                channel_scope="mixed",
                depth="deep",
                output_format="html",
            ),
        }
    ]
    assert json.loads(result.stdout)["scope"] == {
        "channel_scope": "mixed",
        "depth": "deep",
        "output_format": "html",
    }


def test_query_depth_maps_to_search_mode_comprehensive(monkeypatch) -> None:
    calls = _install_cli_spy(monkeypatch, _ok_result())

    result = runner.invoke(
        app,
        ["query", "test", "--depth", "comprehensive", "--no-stream"],
    )

    assert result.exit_code == 0
    assert calls[0]["mode_hint"] is SearchMode.COMPREHENSIVE


def test_query_mode_and_depth_conflict_depth_wins(monkeypatch) -> None:
    calls = _install_cli_spy(monkeypatch, _ok_result())

    result = runner.invoke(
        app,
        [
            "query",
            "test",
            "--mode",
            "fast",
            "--depth",
            "comprehensive",
            "--no-stream",
        ],
    )

    assert result.exit_code == 0
    assert calls[0]["mode_hint"] is SearchMode.COMPREHENSIVE
    assert "--mode ignored because --depth was also provided" in result.stderr


def test_query_invalid_depth_is_bad_parameter() -> None:
    result = runner.invoke(app, ["query", "test", "--depth", "bogus"])

    assert result.exit_code == 2
    assert "Error" in result.stderr


def test_query_invalid_languages_is_bad_parameter() -> None:
    result = runner.invoke(app, ["query", "test", "--languages", "bogus"])

    assert result.exit_code == 2
    assert "channel_scope" in result.stderr


def test_query_format_html_renders_html_output(monkeypatch) -> None:
    markdown = "# Report\n\n| A | B |\n| - | - |\n| 1 | 2 |\n\n```python\nprint('hello')\n```\n"
    _install_cli_spy(monkeypatch, _ok_result(markdown=markdown))

    result = runner.invoke(
        app,
        ["query", "html-test", "--format", "html", "--no-stream"],
    )

    assert result.exit_code == 0
    assert "<!doctype html>" in result.stdout
    assert "<title>html-test</title>" in result.stdout
    assert "<article>" in result.stdout
    assert "<table>" in result.stdout
    assert "<pre><code" in result.stdout


def test_query_format_md_passes_through(monkeypatch) -> None:
    markdown = "# Test\n\nBody"
    _install_cli_spy(monkeypatch, _ok_result(markdown=markdown))

    result = runner.invoke(
        app,
        ["query", "md-test", "--format", "md", "--no-stream"],
    )

    assert result.exit_code == 0
    assert result.stdout == f"{markdown}\n"
    assert "<!doctype html>" not in result.stdout


def test_query_interactive_false_skips_prompt_even_in_tty(monkeypatch) -> None:
    calls = _install_cli_spy(monkeypatch, _ok_result())
    _set_tty(monkeypatch, True)

    import autosearch.cli.main as cli_main

    monkeypatch.setattr(
        cli_main.typer,
        "prompt",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("prompt should not run")),
    )

    result = runner.invoke(
        app,
        ["query", "test", "--depth", "deep", "--no-interactive", "--json"],
    )

    assert result.exit_code == 0
    assert calls[0]["mode_hint"] is SearchMode.DEEP
    assert json.loads(result.stdout)["scope"] == {
        "channel_scope": "all",
        "depth": "deep",
        "output_format": "md",
    }
