"""Gap queue utilities for deep research runs."""

from __future__ import annotations

from typing import Any


def _gap_id(dimension: str) -> str:
    normalized = str(dimension or "").strip().replace(" ", "_").lower()
    return f"gap:{normalized}"


def _missing_dimensions(
    goal_case: dict[str, Any], judge_result: dict[str, Any]
) -> list[str]:
    missing = [
        str(item or "").strip()
        for item in list(judge_result.get("missing_dimensions") or [])
        if str(item or "").strip()
    ]
    if missing:
        return missing
    scores = dict(judge_result.get("dimension_scores") or {})
    if scores:
        return [
            str(key).strip()
            for key, _ in sorted(scores.items(), key=lambda item: int(item[1] or 0))
        ]
    return [
        str((dim or {}).get("id") or "").strip()
        for dim in list(goal_case.get("dimensions") or [])
        if str((dim or {}).get("id") or "").strip()
    ]


def _dimension_weight(goal_case: dict[str, Any], dimension: str) -> int:
    for item in list(goal_case.get("dimensions") or []):
        if str((item or {}).get("id") or "").strip() == str(dimension or "").strip():
            return int((item or {}).get("weight", 0) or 0)
    return 0


def _dimension_close_threshold(goal_case: dict[str, Any], dimension: str) -> int:
    weight = _dimension_weight(goal_case, dimension)
    if weight <= 0:
        return 1
    return max(1, weight // 2)


def _dimension_statuses(
    goal_case: dict[str, Any], judge_result: dict[str, Any]
) -> dict[str, str]:
    explicit_missing = {
        str(item or "").strip()
        for item in list(judge_result.get("missing_dimensions") or [])
        if str(item or "").strip()
    }
    statuses: dict[str, str] = {}
    scores = {
        str(key).strip(): int(value or 0)
        for key, value in dict(judge_result.get("dimension_scores") or {}).items()
        if str(key).strip()
    }
    dimension_ids = [
        str((dim or {}).get("id") or "").strip()
        for dim in list(goal_case.get("dimensions") or [])
        if str((dim or {}).get("id") or "").strip()
    ]
    if not dimension_ids:
        dimension_ids = list(scores.keys())
    for dimension in dimension_ids:
        if dimension in explicit_missing:
            statuses[dimension] = "open"
            continue
        score = int(scores.get(dimension, 0) or 0)
        statuses[dimension] = (
            "open"
            if score < _dimension_close_threshold(goal_case, dimension)
            else "satisfied"
        )
    return statuses


def update_gap_queue(
    *,
    goal_case: dict[str, Any],
    previous_queue: list[dict[str, Any]] | None,
    judge_result: dict[str, Any],
    round_index: int,
) -> list[dict[str, Any]]:
    previous = [dict(item) for item in list(previous_queue or [])]
    queue_by_id = {
        str(item.get("gap_id") or ""): item
        for item in previous
        if str(item.get("gap_id") or "")
    }
    ranked_dimensions = _missing_dimensions(goal_case, judge_result)
    statuses = _dimension_statuses(goal_case, judge_result)
    ranked = {str(key): index for index, key in enumerate(ranked_dimensions, start=1)}

    for dimension, status in statuses.items():
        gap_id = _gap_id(dimension)
        existing = dict(queue_by_id.get(gap_id) or {})
        queue_by_id[gap_id] = {
            "gap_id": gap_id,
            "question": str(dimension).replace("_", " ").strip(),
            "dimension": str(dimension),
            "priority": int(ranked.get(str(dimension), len(ranked) + 1)),
            "status": status,
            "created_round": int(
                existing.get("created_round", round_index) or round_index
            ),
            "last_seen_round": round_index,
        }

    ordered = sorted(
        queue_by_id.values(),
        key=lambda item: (
            0 if str(item.get("status") or "open") == "open" else 1,
            int(item.get("priority", 999) or 999),
            int(item.get("created_round", round_index) or round_index),
        ),
    )
    return ordered


def open_gap_dimensions(
    queue: list[dict[str, Any]] | None, *, limit: int | None = None
) -> list[str]:
    dimensions = [
        str(item.get("dimension") or "").strip()
        for item in list(queue or [])
        if str(item.get("status") or "open") == "open"
        and str(item.get("dimension") or "").strip()
    ]
    if limit is not None:
        return dimensions[:limit]
    return dimensions


def gap_queue_summary(
    queue: list[dict[str, Any]] | None, *, limit: int = 6
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in list(queue or [])[:limit]:
        summary.append(
            {
                "gap_id": str(item.get("gap_id") or ""),
                "dimension": str(item.get("dimension") or ""),
                "status": str(item.get("status") or ""),
                "priority": int(item.get("priority", 0) or 0),
            }
        )
    return summary
