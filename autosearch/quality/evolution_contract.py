"""Validation helpers for AVO self-evolution trial evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

EvolutionVerdict = Literal["improved", "regressed", "unchanged", "invalid"]


@dataclass(frozen=True)
class NativeCodexComparison:
    """Evidence from running the same task with native Codex before AutoSearch."""

    query: str
    raw_output: str
    result_count_by_type: Mapping[str, int]
    conceptual_framework_depth: int
    coverage_gaps: Sequence[str]
    provider: str = "native_codex"
    artifact_path: str | None = None


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
    evidence_refs: Mapping[str, str] = field(default_factory=dict)


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
            query=str(native_payload.get("query") or ""),
            raw_output=str(native_payload.get("raw_output") or ""),
            result_count_by_type=_coerce_result_counts(native_payload.get("result_count_by_type")),
            conceptual_framework_depth=_coerce_framework_depth(
                native_payload.get("conceptual_framework_depth")
            ),
            coverage_gaps=tuple(str(gap) for gap in native_payload.get("coverage_gaps", ())),
            provider=str(native_payload.get("provider") or "native_codex"),
            artifact_path=_optional_string(native_payload.get("artifact_path")),
        )

    return EvolutionTrial(
        baseline_score=_optional_score(payload.get("baseline_score")),
        revised_score=_optional_score(payload.get("revised_score")),
        skill_modified=_coerce_bool(payload.get("skill_modified")),
        committed=_coerce_bool(payload.get("committed")),
        reverted=_coerce_bool(payload.get("reverted")),
        pattern_written=_coerce_bool(payload.get("pattern_written")),
        native_codex_baseline=native_baseline,
        evidence_refs=_coerce_evidence_refs(payload.get("evidence_refs")),
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
    if not comparison.query.strip():
        failures.append("native Codex baseline must include the same query")
    if not comparison.raw_output.strip() and not (comparison.artifact_path or "").strip():
        failures.append("native Codex baseline must include raw output or an artifact path")
    if not comparison.result_count_by_type:
        failures.append("native Codex baseline must include result counts by type")
    elif any(count < 0 for count in comparison.result_count_by_type.values()):
        failures.append("native Codex baseline result counts must be non-negative")
    if comparison.conceptual_framework_depth < 0:
        failures.append("native Codex baseline must include conceptual framework depth")
    elif comparison.conceptual_framework_depth == 0:
        failures.append("native Codex baseline conceptual framework depth must be positive")
    if not any(gap.strip() for gap in comparison.coverage_gaps):
        failures.append("native Codex baseline must include at least one coverage gap")


def _coerce_result_counts(value: Any) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, int] = {}
    for key, count in value.items():
        if isinstance(count, bool) or not isinstance(count, int | float):
            continue
        result[str(key)] = int(count)
    return result


def _coerce_framework_depth(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return -1
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value) and value >= 0 and value.is_integer():
            return int(value)
        return -1
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = float(text)
        except ValueError:
            return -1
        if math.isfinite(parsed) and parsed >= 0 and parsed.is_integer():
            return int(parsed)
    return -1


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return False


def _coerce_evidence_refs(value: Any) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(ref) for key, ref in value.items() if ref is not None}


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


__all__ = [
    "EvolutionTrial",
    "EvolutionValidationResult",
    "NativeCodexComparison",
    "trial_from_mapping",
    "validate_evolution_trial",
]
