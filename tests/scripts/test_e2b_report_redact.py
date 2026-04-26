from __future__ import annotations

from pathlib import Path

from scripts.e2b import report, run_comprehensive_tests
from scripts.e2b.evaluate import compute_summary
from scripts.e2b.sandbox_runner import ScenarioResult


FAKE_API_KEY = "sk-" + "FAKEKEY1234567890abcdef"


def _scenario_with_secret_error() -> ScenarioResult:
    return ScenarioResult(
        scenario_id="A1",
        category="A",
        name="fake_secret_error",
        score=0,
        passed=False,
        details={},
        error=f"request failed with {FAKE_API_KEY}",
        duration_s=1.2,
    )


def _scenario_with_secret_transcript() -> ScenarioResult:
    return ScenarioResult(
        scenario_id="A2",
        category="A",
        name="fake_secret_transcript",
        score=0,
        passed=False,
        details={
            "stderr": f"stderr leaked {FAKE_API_KEY}",
            "transcript": [
                {"role": "assistant", "content": f"traceback leaked {FAKE_API_KEY}"},
            ],
        },
        error=f"scenario failed with {FAKE_API_KEY}",
        duration_s=2.3,
    )


def _summary_for(result: ScenarioResult) -> dict:
    return compute_summary([result])


def test_scenario_error_redacted_in_summary(tmp_path: Path) -> None:
    scenario = _scenario_with_secret_error()

    report.render([scenario], _summary_for(scenario), tmp_path)

    content = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert FAKE_API_KEY not in content
    assert "[REDACTED]" in content


def test_scenario_error_redacted_in_results_json(tmp_path: Path) -> None:
    scenario = _scenario_with_secret_error()

    report.render_results_json([scenario], _summary_for(scenario), tmp_path)

    content = (tmp_path / "results.json").read_text(encoding="utf-8")
    assert FAKE_API_KEY not in content
    assert "[REDACTED]" in content


def test_comprehensive_transcripts_redacted(tmp_path: Path) -> None:
    scenario = _scenario_with_secret_transcript()

    run_comprehensive_tests.write_outputs([scenario], tmp_path)

    for path in (tmp_path / "summary.md", tmp_path / "results.json"):
        content = path.read_text(encoding="utf-8")
        assert FAKE_API_KEY not in content
        assert "[REDACTED]" in content
