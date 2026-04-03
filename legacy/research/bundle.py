"""Explicit research bundle contract."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


def _bundle_id(goal_id: str, evidence_records: list[dict[str, Any]]) -> str:
    urls = "\n".join(
        sorted(str(item.get("url") or "") for item in list(evidence_records or []))
    )
    raw = f"{goal_id}\n{urls}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


@dataclass
class ResearchBundle:
    goal_id: str
    bundle_id: str
    evidence_records: list[dict[str, Any]] = field(default_factory=list)
    dimension_scores: dict[str, int] = field(default_factory=dict)
    missing_dimensions: list[str] = field(default_factory=list)
    matched_dimensions: list[str] = field(default_factory=list)
    score: int = 0
    judge: str = ""
    score_gap: int = 0

    @classmethod
    def from_parts(
        cls,
        *,
        goal_id: str,
        evidence_records: list[dict[str, Any]],
        judge_result: dict[str, Any],
        target_score: int = 100,
    ) -> "ResearchBundle":
        normalized_goal_id = str(goal_id or "goal")
        return cls(
            goal_id=normalized_goal_id,
            bundle_id=_bundle_id(normalized_goal_id, evidence_records),
            evidence_records=list(evidence_records or []),
            dimension_scores={
                str(key): int(value or 0)
                for key, value in dict(
                    judge_result.get("dimension_scores") or {}
                ).items()
            },
            missing_dimensions=[
                str(item) for item in list(judge_result.get("missing_dimensions") or [])
            ],
            matched_dimensions=[
                str(item) for item in list(judge_result.get("matched_dimensions") or [])
            ],
            score=int(judge_result.get("score", 0) or 0),
            judge=str(judge_result.get("judge") or ""),
            score_gap=max(
                int(target_score or 100) - int(judge_result.get("score", 0) or 0), 0
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
