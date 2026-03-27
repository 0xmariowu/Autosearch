"""Narrative diary for multi-round research runs."""

from __future__ import annotations

from typing import Any


def summarize_diary(
    entries: list[dict[str, Any]] | None, *, limit: int = 5
) -> list[str]:
    summary: list[str] = []
    for item in list(entries or [])[-limit:]:
        round_index = int(item.get("round_index", 0) or 0)
        role = str(item.get("role") or "").strip()
        score = int(item.get("score", 0) or 0)
        weakest = str(item.get("weakest_dimension") or "").strip()
        parts = [f"round {round_index}"]
        if role:
            parts.append(role)
        parts.append(f"score={score}")
        if weakest:
            parts.append(f"weakest={weakest}")
        summary.append(" | ".join(parts))
    return summary


def build_diary_entry(
    *,
    round_index: int,
    label: str,
    role: str,
    decision: dict[str, Any],
    planning_ops: list[dict[str, Any]],
    judge_result: dict[str, Any],
    harness_metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "round_index": round_index,
        "label": str(label or ""),
        "role": str(role or ""),
        "score": int(judge_result.get("score", 0) or 0),
        "weakest_dimension": (
            min(
                sorted((judge_result.get("dimension_scores") or {}).keys()),
                key=lambda key: int(
                    (judge_result.get("dimension_scores") or {}).get(key, 0) or 0
                ),
            )
            if (judge_result.get("dimension_scores") or {})
            else ""
        ),
        "decision_rationale": str(decision.get("rationale") or ""),
        "cross_verify": bool(decision.get("cross_verify")),
        "planning_ops": [
            {"op": str(item.get("op") or ""), "target": str(item.get("target") or "")}
            for item in list(planning_ops or [])
        ],
        "new_unique_urls": int(harness_metrics.get("new_unique_urls", 0) or 0),
        "novelty_ratio": float(harness_metrics.get("novelty_ratio", 0.0) or 0.0),
    }
