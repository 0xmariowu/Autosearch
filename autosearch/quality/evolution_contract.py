"""Validation helpers for AVO self-evolution trial evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

EvolutionVerdict = Literal["improved", "regressed", "unchanged", "invalid"]


@dataclass(frozen=True)
class NativeCodexComparison:
    """Evidence from running the same task with native Codex before AutoSearch."""

    result_count_by_type: Mapping[str, int]
    conceptual_framework_depth: int
    coverage_gaps: Sequence[str]


@dataclass(frozen=True)
class EvolutionTrial:
    """One auditable AVO evolution attempt, including scores and side effects."""

    baseline_score: float | int | None
    revised_score: float | int | None
    skill_modified: bool
    committed: bool
    reverted: bool
    pattern_written: bool
    native_codex_baseline: NativeCodexComparison | None


@dataclass(frozen=True)
class EvolutionValidationResult:
    """Outcome of validating an AVO trial against the repository evolution contract."""

    ok: bool
    verdict: EvolutionVerdict
    improvement_delta: float | None
    failures: tuple[str, ...]


def trial_from_mapping(payload: Mapping[str, Any]) -> EvolutionTrial:
    """Build an ``EvolutionTrial`` from a JSON-like report payload."""

    native_payload = payload.get("native_codex_baseline")
    native_baseline = None
    if isinstance(native_payload, Mapping):
        native_baseline = NativeCodexComparison(
            result_count_by_type=_coerce_result_counts(native_payload.get("result_count_by_type")),
            conceptual_framework_depth=int(native_payload.get("conceptual_framework_depth", -1)),
            coverage_gaps=tuple(str(gap) for gap in native_payload.get("coverage_gaps", ())),
        )

    return EvolutionTrial(
        baseline_score=_optional_score(payload.get("baseline_score")),
        revised_score=_optional_score(payload.get("revised_score")),
        skill_modified=bool(payload.get("skill_modified", False)),
        committed=bool(payload.get("committed", False)),
        reverted=bool(payload.get("reverted", False)),
        pattern_written=bool(payload.get("pattern_written", False)),
        native_codex_baseline=native_baseline,
    )


def validate_evolution_trial(
    trial: EvolutionTrial,
    *,
    min_improvement_delta: float = 0.0,
) -> EvolutionValidationResult:
    """Validate that a self-evolution run has the evidence required by Rule 21/22."""

    failures: list[str] = []
    baseline_score = _valid_score(trial.baseline_score, "baseline_score", failures)
    revised_score = _valid_score(trial.revised_score, "revised_score", failures)

    if not trial.skill_modified:
        failures.append("agent-initiated skill modification is required")
    if not trial.pattern_written:
        failures.append("pattern state write is required")

    _validate_native_codex_baseline(trial.native_codex_baseline, failures)

    delta: float | None = None
    verdict: EvolutionVerdict = "invalid"
    if baseline_score is not None and revised_score is not None:
        delta = revised_score - baseline_score
        if delta > min_improvement_delta:
            verdict = "improved"
            if not trial.committed:
                failures.append("improving trials must be committed")
        elif delta < 0:
            verdict = "regressed"
            if not trial.reverted:
                failures.append("non-improving trials must be reverted")
        else:
            verdict = "unchanged"
            if not trial.reverted:
                failures.append("non-improving trials must be reverted")

    return EvolutionValidationResult(
        ok=not failures,
        verdict=verdict,
        improvement_delta=delta,
        failures=tuple(failures),
    )


def _optional_score(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    return None


def _valid_score(
    value: float | int | None,
    field_name: str,
    failures: list[str],
) -> float | None:
    if value is None:
        failures.append(f"{field_name} is required")
        return None
    score = float(value)
    if not math.isfinite(score) or score < 0:
        failures.append(f"{field_name} must be a finite non-negative number")
        return None
    return score


def _validate_native_codex_baseline(
    comparison: NativeCodexComparison | None,
    failures: list[str],
) -> None:
    if comparison is None:
        failures.append("native Codex baseline comparison is required")
        return
    if not comparison.result_count_by_type:
        failures.append("native Codex baseline must include result counts by type")
    if comparison.conceptual_framework_depth < 0:
        failures.append("native Codex baseline must include conceptual framework depth")


def _coerce_result_counts(value: Any) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, int] = {}
    for key, count in value.items():
        if isinstance(count, bool) or not isinstance(count, int | float):
            continue
        result[str(key)] = int(count)
    return result


__all__ = [
    "EvolutionTrial",
    "EvolutionValidationResult",
    "NativeCodexComparison",
    "trial_from_mapping",
    "validate_evolution_trial",
]
