import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

import autosearch.skills.experience as exp_mod
from autosearch.quality.evolution_contract import (
    EvolutionTrial,
    NativeCodexComparison,
    trial_from_mapping,
    validate_evolution_trial,
)
from scripts.e2b.scenarios.k_avo_evolution import _format_k5_error


def _native_baseline() -> NativeCodexComparison:
    return NativeCodexComparison(
        query="same AVO validation query",
        raw_output="Native Codex answer with direct analysis but no persistent skill memory.",
        result_count_by_type={"docs": 2, "community": 1},
        conceptual_framework_depth=2,
        coverage_gaps=("misses Chinese community discussions",),
    )


def test_improving_trial_requires_commit_and_native_codex_baseline() -> None:
    trial = EvolutionTrial(
        baseline_score=0.42,
        revised_score=0.67,
        skill_modified=True,
        committed=True,
        reverted=False,
        pattern_written=True,
        native_codex_baseline=_native_baseline(),
    )

    result = validate_evolution_trial(trial)

    assert result.ok
    assert result.verdict == "improved"
    assert result.improvement_delta == pytest.approx(0.25)


def test_missing_native_codex_baseline_blocks_validation() -> None:
    trial = EvolutionTrial(
        baseline_score=0.42,
        revised_score=0.67,
        skill_modified=True,
        committed=True,
        reverted=False,
        pattern_written=True,
        native_codex_baseline=None,
    )

    result = validate_evolution_trial(trial)

    assert not result.ok
    assert "native Codex baseline comparison is required" in result.failures


def test_regressing_trial_requires_revert() -> None:
    trial = EvolutionTrial(
        baseline_score=0.80,
        revised_score=0.70,
        skill_modified=True,
        committed=False,
        reverted=False,
        pattern_written=True,
        native_codex_baseline=_native_baseline(),
    )

    result = validate_evolution_trial(trial)

    assert not result.ok
    assert result.verdict == "regressed"
    assert "non-improving trials must be reverted" in result.failures


def test_mapping_loader_accepts_json_report_shape() -> None:
    trial = trial_from_mapping(
        {
            "baseline_score": 12,
            "revised_score": 18,
            "skill_modified": True,
            "committed": True,
            "pattern_written": True,
            "native_codex_baseline": {
                "query": "same query",
                "raw_output": "raw native baseline output",
                "result_count_by_type": {"answer": 1, "source": 3},
                "conceptual_framework_depth": 3,
                "coverage_gaps": ["missing persistent skill lineage"],
                "provider": "native_codex_cli",
            },
            "evidence_refs": {
                "skill_path": "/tmp/repo/autosearch/skills/channels/arxiv/SKILL.md",
                "commit_sha": "abc123",
                "ignored_none": None,
            },
        }
    )

    assert validate_evolution_trial(trial).ok
    assert trial.evidence_refs["commit_sha"] == "abc123"
    assert "ignored_none" not in trial.evidence_refs


def test_mapping_loader_does_not_treat_false_strings_as_true() -> None:
    trial = trial_from_mapping(
        {
            "baseline_score": 12,
            "revised_score": 18,
            "skill_modified": "false",
            "committed": "false",
            "reverted": "false",
            "pattern_written": "false",
            "native_codex_baseline": {
                "query": "same query",
                "raw_output": "raw native baseline output",
                "result_count_by_type": {"answer": 1},
                "conceptual_framework_depth": 1,
                "coverage_gaps": ["missing persistent skill lineage"],
            },
        }
    )

    assert trial.skill_modified is False
    assert trial.committed is False
    assert trial.reverted is False
    assert trial.pattern_written is False


def test_mapping_loader_rejects_invalid_framework_depth_without_raising() -> None:
    trial = trial_from_mapping(
        {
            "baseline_score": 12,
            "revised_score": 18,
            "skill_modified": True,
            "committed": True,
            "pattern_written": True,
            "native_codex_baseline": {
                "query": "same query",
                "raw_output": "raw native baseline output",
                "result_count_by_type": {"answer": 1},
                "conceptual_framework_depth": "deep",
                "coverage_gaps": ["missing persistent skill lineage"],
            },
        }
    )

    result = validate_evolution_trial(trial)

    assert not result.ok
    assert "native Codex baseline must include conceptual framework depth" in result.failures


def test_mapping_loader_accepts_integer_like_framework_depth_values() -> None:
    for depth in (3.0, "+3", "3.0"):
        trial = trial_from_mapping(
            {
                "baseline_score": 12,
                "revised_score": 18,
                "skill_modified": True,
                "committed": True,
                "pattern_written": True,
                "native_codex_baseline": {
                    "query": "same query",
                    "raw_output": "raw native baseline output",
                    "result_count_by_type": {"answer": 1},
                    "conceptual_framework_depth": depth,
                    "coverage_gaps": ["missing persistent skill lineage"],
                },
            }
        )

        assert trial.native_codex_baseline is not None
        assert trial.native_codex_baseline.conceptual_framework_depth == 3


def test_weak_native_baseline_evidence_is_rejected() -> None:
    result = validate_evolution_trial(
        EvolutionTrial(
            baseline_score=0,
            revised_score=1,
            skill_modified=True,
            committed=True,
            reverted=False,
            pattern_written=True,
            native_codex_baseline=NativeCodexComparison(
                query="",
                raw_output="",
                result_count_by_type={"answer": -1},
                conceptual_framework_depth=0,
                coverage_gaps=(),
            ),
        )
    )

    assert not result.ok
    assert "native Codex baseline must include the same query" in result.failures
    assert "native Codex baseline must include raw output or an artifact path" in result.failures
    assert "native Codex baseline result counts must be non-negative" in result.failures
    assert "native Codex baseline conceptual framework depth must be positive" in result.failures
    assert "native Codex baseline must include at least one coverage gap" in result.failures


def test_evolution_contract_scenario_registered_in_e2b_suite() -> None:
    from scripts.e2b.run_comprehensive_tests import ALL_SCENARIOS
    from scripts.e2b.scenarios.k_avo_evolution import k5_evolution_contract_validation

    assert ("K5", "K", k5_evolution_contract_validation) in ALL_SCENARIOS


def test_real_git_workspace_trial_validates_commit_revert_and_pattern_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    skill_path = repo / "autosearch" / "skills" / "channels" / "arxiv" / "SKILL.md"
    runtime_root = repo / ".avo-experience"
    patterns_path = runtime_root / "channels" / "arxiv" / "experience" / "patterns.jsonl"
    marker = "AVO_TMP_REAL_TRIAL_RULE"

    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        "\n".join(
            [
                "---",
                "name: arxiv",
                "description: Search arXiv.",
                "---",
                "# Strategy",
                "Use precise academic terms.",
                "# Quality Bar",
                "Return relevant papers.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _git(repo, "init")
    _git(repo, "config", "user.name", "AVO Test")
    _git(repo, "config", "user.email", "avo-test@example.com")
    _git(repo, "add", str(skill_path.relative_to(repo)))
    _git(repo, "commit", "-m", "test: seed skill")

    baseline_score = _evidence_score(skill_path.read_text(encoding="utf-8"))
    skill_path.write_text(
        skill_path.read_text(encoding="utf-8")
        + "\n## AVO Trial Evidence\n"
        + f"- {marker}: record baseline score, native Codex baseline, re-score, "
        + "patterns.jsonl write, and git commit / git revert evidence.\n",
        encoding="utf-8",
    )
    modified_text = skill_path.read_text(encoding="utf-8")
    revised_score = _evidence_score(modified_text)
    skill_modified = marker in modified_text

    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(runtime_root))
    monkeypatch.setattr(exp_mod, "_SKILLS_ROOT", repo / "autosearch" / "skills")
    exp_mod.append_event(
        "arxiv",
        {
            "skill": "arxiv",
            "query": "tmp real trial",
            "outcome": "success",
            "winning_pattern": marker,
            "ts": datetime.now(UTC).isoformat(),
        },
    )

    _git(repo, "add", str(skill_path.relative_to(repo)))
    _git(repo, "commit", "-m", "test: AVO real trial")
    _git(repo, "revert", "HEAD", "--no-edit")

    final_text = skill_path.read_text(encoding="utf-8")
    result = validate_evolution_trial(
        EvolutionTrial(
            baseline_score=baseline_score,
            revised_score=revised_score,
            skill_modified=skill_modified,
            committed="test: AVO real trial" in _git(repo, "log", "--oneline", "-2").stdout,
            reverted="Revert" in _git(repo, "log", "--oneline", "-1").stdout,
            pattern_written=marker in patterns_path.read_text(encoding="utf-8"),
            native_codex_baseline=_native_baseline(),
            evidence_refs={
                "skill_path": str(skill_path),
                "pattern_path": str(patterns_path),
                "commit_log": _git(repo, "log", "--oneline", "-2").stdout,
                "revert_log": _git(repo, "log", "--oneline", "-1").stdout,
            },
        )
    )

    assert result.ok
    assert result.verdict == "improved"
    assert revised_score > baseline_score
    assert marker not in final_text
    assert result.failures == ()


def test_k5_error_summary_promotes_failures_for_agents() -> None:
    summary = _format_k5_error(
        {
            "validation_ok": False,
            "commit_ok": False,
            "revert_ok": True,
            "validation_failures": ["native Codex baseline comparison is required"],
            "git": {"commit_stderr": "nothing to commit, working tree clean"},
        }
    )

    assert "native Codex baseline comparison is required" in summary
    assert "git commit failed" in summary
    assert "nothing to commit" in summary


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result


def _evidence_score(text: str) -> int:
    checks = [
        text.startswith("---"),
        "# Quality Bar" in text,
        "native Codex baseline" in text,
        "baseline score" in text and "re-score" in text,
        "git commit" in text and "git revert" in text,
        "patterns.jsonl" in text,
    ]
    return sum(20 for check in checks if check)
