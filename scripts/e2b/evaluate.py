"""Scoring and evaluation for E2B comprehensive tests."""

from __future__ import annotations

from collections import defaultdict

from scripts.e2b.sandbox_runner import ScenarioResult

# Category weights in the final score
_CATEGORY_WEIGHTS = {
    "A": 0.15,
    "B": 0.10,
    "C": 0.10,
    "D": 0.10,
    "E": 0.05,
    "F": 0.05,
    "G": 0.10,
    "H": 0.10,
    "I": 0.10,
    "J": 0.05,
    "K": 0.05,
    "L": 0.05,
    # W: bonus only — not scored
}

_READINESS_THRESHOLD = 80
_BETA_THRESHOLD = 60


def compute_summary(results: list[ScenarioResult]) -> dict:
    by_category: dict[str, list[ScenarioResult]] = defaultdict(list)
    for r in results:
        by_category[r.category].append(r)

    category_scores: dict[str, float] = {}
    for cat, cat_results in by_category.items():
        if cat == "W":
            continue
        if cat_results:
            category_scores[cat] = sum(r.score for r in cat_results) / len(cat_results)

    # Weighted overall score
    total_weight = sum(_CATEGORY_WEIGHTS.get(c, 0.1) for c in category_scores)
    if total_weight > 0:
        overall = (
            sum(category_scores.get(c, 0) * _CATEGORY_WEIGHTS.get(c, 0.1) for c in category_scores)
            / total_weight
        )
    else:
        overall = 0.0

    passed = sum(1 for r in results if r.passed and r.category != "W")
    total_scored = len([r for r in results if r.category != "W"])
    total_ev = sum(r.evidence_count for r in results)
    total_report = sum(r.report_length for r in results)

    if overall >= _READINESS_THRESHOLD:
        readiness = "READY"
    elif overall >= _BETA_THRESHOLD:
        readiness = "BETA"
    else:
        readiness = "NOT_READY"

    summary = {
        "overall_score": round(overall, 1),
        "readiness": readiness,
        "passed": passed,
        "total": total_scored,
        "pass_rate": round(passed / total_scored * 100, 1) if total_scored else 0,
        "total_evidence": total_ev,
        "total_report_chars": total_report,
        "category_scores": {k: round(v, 1) for k, v in sorted(category_scores.items())},
        "failures": [
            {"id": r.scenario_id, "name": r.name, "score": r.score, "error": r.error[:100]}
            for r in results
            if not r.passed and r.category != "W"
        ],
    }

    bonus = [r for r in results if r.category == "W"]
    summary["bonus_results"] = [r.to_dict() for r in bonus]
    summary["bonus_passed"] = sum(1 for r in bonus if r.passed)
    summary["bonus_total"] = len(bonus)
    return summary
