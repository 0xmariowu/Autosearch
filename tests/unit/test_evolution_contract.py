import pytest

from autosearch.quality.evolution_contract import (
    EvolutionTrial,
    NativeCodexComparison,
    trial_from_mapping,
    validate_evolution_trial,
)


def _native_baseline() -> NativeCodexComparison:
    return NativeCodexComparison(
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
                "result_count_by_type": {"answer": 1, "source": 3},
                "conceptual_framework_depth": 3,
                "coverage_gaps": [],
            },
        }
    )

    assert validate_evolution_trial(trial).ok


def test_evolution_contract_scenario_registered_in_e2b_suite() -> None:
    from scripts.e2b.run_comprehensive_tests import ALL_SCENARIOS
    from scripts.e2b.scenarios.k_avo_evolution import k5_evolution_contract_validation

    assert ("K5", "K", k5_evolution_contract_validation) in ALL_SCENARIOS
