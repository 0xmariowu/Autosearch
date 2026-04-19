# Self-written for F102 CLI interactive prompt flow
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

runner = CliRunner()


def _ok_result() -> PipelineResult:
    return PipelineResult(
        delivery_status="ok",
        clarification=ClarifyResult(
            need_clarification=False,
            question=None,
            verification="Enough information to proceed.",
            rubrics=[],
            mode=SearchMode.FAST,
        ),
        markdown="# Test\n\nBody",
        quality=EvaluationResult(
            grade=GradeOutcome.PASS,
            follow_up_gaps=[],
        ),
        iterations=1,
    )


def _install_cli_spy(monkeypatch, pipeline_result: PipelineResult) -> list[SearchMode | None]:
    import autosearch.cli.main as cli_main

    calls: list[SearchMode | None] = []

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
            scope=None,
        ) -> PipelineResult:
            _ = query
            _ = scope
            calls.append(mode_hint)
            return pipeline_result

    monkeypatch.setattr(cli_main, "Pipeline", StubPipeline)
    monkeypatch.setattr(cli_main, "LLMClient", lambda: object())
    monkeypatch.setattr(cli_main, "_build_channels", lambda: [object()])

    return calls


def _set_tty(monkeypatch, value: bool) -> None:
    monkeypatch.setattr(click.testing._NamedTextIOWrapper, "isatty", lambda self: value)


def test_interactive_prompts_for_missing_fields(monkeypatch) -> None:
    calls = _install_cli_spy(monkeypatch, _ok_result())
    _set_tty(monkeypatch, True)

    import autosearch.cli.main as cli_main

    prompts: list[str] = []
    answers = iter(["mixed", "comprehensive", "html"])

    def fake_prompt(text: str) -> str:
        prompts.append(text)
        return next(answers)

    monkeypatch.setattr(cli_main.typer, "prompt", fake_prompt)

    result = runner.invoke(app, ["query", "test", "--interactive", "--json"])

    assert result.exit_code == 0
    assert len(prompts) == 3
    assert calls == [SearchMode.COMPREHENSIVE]
    assert json.loads(result.stdout)["scope"] == {
        "channel_scope": "mixed",
        "depth": "comprehensive",
        "output_format": "html",
    }


def test_interactive_accepts_index_or_value(monkeypatch) -> None:
    calls = _install_cli_spy(monkeypatch, _ok_result())
    _set_tty(monkeypatch, True)

    import autosearch.cli.main as cli_main

    answers = iter(["zh_only", "2", "2"])
    monkeypatch.setattr(cli_main.typer, "prompt", lambda text: next(answers))

    result = runner.invoke(app, ["query", "test", "--interactive", "--json"])

    assert result.exit_code == 0
    assert calls == [SearchMode.DEEP]
    assert json.loads(result.stdout)["scope"] == {
        "channel_scope": "zh_only",
        "depth": "deep",
        "output_format": "html",
    }


def test_interactive_rejects_invalid_answer_three_times_then_exits(monkeypatch) -> None:
    calls = _install_cli_spy(monkeypatch, _ok_result())
    _set_tty(monkeypatch, True)

    import autosearch.cli.main as cli_main

    answers = iter(["bogus", "bogus", "bogus"])
    monkeypatch.setattr(cli_main.typer, "prompt", lambda text: next(answers))

    result = runner.invoke(app, ["query", "test", "--interactive", "--json"])

    assert result.exit_code == 2
    assert calls == []


def test_interactive_skipped_when_not_tty(monkeypatch) -> None:
    calls = _install_cli_spy(monkeypatch, _ok_result())
    _set_tty(monkeypatch, False)

    import autosearch.cli.main as cli_main

    monkeypatch.setattr(
        cli_main.typer,
        "prompt",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("prompt should not run")),
    )

    result = runner.invoke(app, ["query", "test", "--json"])

    assert result.exit_code == 0
    assert calls == [SearchMode.FAST]
    assert json.loads(result.stdout)["scope"] == {
        "channel_scope": "all",
        "depth": "fast",
        "output_format": "md",
    }


def test_interactive_skipped_in_json_mode(monkeypatch) -> None:
    calls = _install_cli_spy(monkeypatch, _ok_result())
    _set_tty(monkeypatch, True)

    import autosearch.cli.main as cli_main

    monkeypatch.setattr(
        cli_main.typer,
        "prompt",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("prompt should not run")),
    )

    result = runner.invoke(app, ["query", "test", "--json"])

    assert result.exit_code == 0
    assert calls == [SearchMode.FAST]
    assert json.loads(result.stdout)["scope"] == {
        "channel_scope": "all",
        "depth": "fast",
        "output_format": "md",
    }
