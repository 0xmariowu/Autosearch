# Self-written, plan v2.3 § 13.5
import asyncio
import json

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


def _ok_result(channel_empty_calls: dict[str, int] | None = None) -> PipelineResult:
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
        iterations=2,
        channel_empty_calls=channel_empty_calls or {},
    )


def _clarification_result() -> PipelineResult:
    return PipelineResult(
        delivery_status="needs_clarification",
        clarification=ClarifyResult(
            need_clarification=True,
            question="Which deployment target do you care about?",
            verification=None,
            rubrics=[],
            mode=SearchMode.DEEP,
        ),
        iterations=0,
    )


class _StubChannel:
    def __init__(self, name: str = "demo") -> None:
        self.name = name


class _StubLLMClient:
    pass


def _install_cli_stubs(monkeypatch, pipeline_result: PipelineResult) -> None:
    import autosearch.cli.main as cli_main

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
            _ = mode_hint
            _ = scope
            if self.on_event is not None:
                maybe_coro = self.on_event({"type": "phase", "phase": "M0", "status": "start"})
                if asyncio.iscoroutine(maybe_coro):
                    await maybe_coro
            return pipeline_result

    monkeypatch.setattr(cli_main, "Pipeline", StubPipeline)
    monkeypatch.setattr(cli_main, "LLMClient", _StubLLMClient)
    monkeypatch.setattr(cli_main, "_build_channels", lambda: [_StubChannel()])


def test_cli_query_prints_markdown_for_ok_result(monkeypatch) -> None:
    _install_cli_stubs(monkeypatch, _ok_result())

    result = runner.invoke(app, ["query", "test", "--no-stream"])

    assert result.exit_code == 0
    assert result.stdout == "# Test\n\nBody\n"
    assert result.stderr == ""


def test_cli_bare_query_routes_to_query_command(monkeypatch) -> None:
    _install_cli_stubs(monkeypatch, _ok_result())

    result = runner.invoke(app, ["test", "--no-stream"])

    assert result.exit_code == 0
    assert result.stdout == "# Test\n\nBody\n"
    assert result.stderr == ""


def test_cli_query_stream_writes_event_json_to_stderr(monkeypatch) -> None:
    _install_cli_stubs(monkeypatch, _ok_result())

    result = runner.invoke(app, ["query", "test"])

    assert result.exit_code == 0
    assert result.stdout == "# Test\n\nBody\n"
    assert json.loads(result.stderr.strip().splitlines()[0]) == {
        "type": "phase",
        "phase": "M0",
        "status": "start",
    }


def test_cli_query_json_outputs_machine_readable_envelope(monkeypatch) -> None:
    _install_cli_stubs(monkeypatch, _ok_result())

    result = runner.invoke(app, ["query", "test", "--json"])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "delivery_status": "ok",
        "markdown": "# Test\n\nBody",
        "iterations": 2,
        "channel_empty_calls": {},
        "quality_grade": "pass",
        "sources": [],
        "scope": {
            "domain_followups": [],
            "channel_scope": "all",
            "depth": "fast",
            "output_format": "md",
        },
    }


def test_cli_json_output_includes_channel_empty_calls(monkeypatch) -> None:
    _install_cli_stubs(monkeypatch, _ok_result(channel_empty_calls={"arxiv": 3}))

    result = runner.invoke(app, ["query", "test", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["channel_empty_calls"] == {"arxiv": 3}


def test_cli_query_exits_two_for_needs_clarification(monkeypatch) -> None:
    _install_cli_stubs(monkeypatch, _clarification_result())

    result = runner.invoke(app, ["query", "test", "--no-stream"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == "Which deployment target do you care about?\n"
