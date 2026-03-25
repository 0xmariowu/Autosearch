"""Gap queue utilities for deep research runs."""

from __future__ import annotations

from typing import Any


def _gap_id(dimension: str) -> str:
    normalized = str(dimension or "").strip().replace(" ", "_").lower()
    return f"gap:{normalized}"


def _missing_dimensions(goal_case: dict[str, Any], judge_result: dict[str, Any]) -> list[str]:
    missing = [str(item or "").strip() for item in list(judge_result.get("missing_dimensions") or []) if str(item or "").strip()]
    if missing:
        return missing
    scores = dict(judge_result.get("dimension_scores") or {})
    if scores:
        return [str(key).strip() for key, _ in sorted(scores.items(), key=lambda item: int(item[1] or 0))]
    return [
        str((dim or {}).get("id") or "").strip()
        for dim in list(goal_case.get("dimensions") or [])
        if str((dim or {}).get("id") or "").strip()
    ]


def update_gap_queue(
    *,
    goal_case: dict[str, Any],
    previous_queue: list[dict[str, Any]] | None,
    judge_result: dict[str, Any],
    round_index: int,
) -> list[dict[str, Any]]:
    previous = [dict(item) for item in list(previous_queue or [])]
    queue_by_id = {str(item.get("gap_id") or ""): item for item in previous if str(item.get("gap_id") or "")}
    missing = _missing_dimensions(goal_case, judge_result)
    missing_set = {str(item) for item in missing}
    ranked = {str(key): index for index, key in enumerate(missing, start=1)}

    for dimension in missing:
        gap_id = _gap_id(dimension)
        existing = dict(queue_by_id.get(gap_id) or {})
        queue_by_id[gap_id] = {
            "gap_id": gap_id,
            "question": str(dimension).replace("_", " ").strip(),
            "dimension": str(dimension),
            "priority": int(ranked.get(str(dimension), len(ranked) + 1)),
            "status": "open",
            "created_round": int(existing.get("created_round", round_index) or round_index),
            "last_seen_round": round_index,
        }

    for gap_id, item in list(queue_by_id.items()):
        dimension = str(item.get("dimension") or "")
        if dimension not in missing_set and item.get("status") == "open":
            item["status"] = "satisfied"
            item["last_seen_round"] = round_index
            queue_by_id[gap_id] = item

    ordered = sorted(
        queue_by_id.values(),
        key=lambda item: (
            0 if str(item.get("status") or "open") == "open" else 1,
            int(item.get("priority", 999) or 999),
            int(item.get("created_round", round_index) or round_index),
        ),
    )
    return ordered


def open_gap_dimensions(queue: list[dict[str, Any]] | None, *, limit: int | None = None) -> list[str]:
    dimensions = [
        str(item.get("dimension") or "").strip()
        for item in list(queue or [])
        if str(item.get("status") or "open") == "open" and str(item.get("dimension") or "").strip()
    ]
    if limit is not None:
        return dimensions[:limit]
    return dimensions


def gap_queue_summary(queue: list[dict[str, Any]] | None, *, limit: int = 6) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in list(queue or [])[:limit]:
        summary.append({
            "gap_id": str(item.get("gap_id") or ""),
            "dimension": str(item.get("dimension") or ""),
            "status": str(item.get("status") or ""),
            "priority": int(item.get("priority", 0) or 0),
        })
    return summary
