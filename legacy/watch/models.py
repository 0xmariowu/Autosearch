"""Models for independent goal watches."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GoalWatch:
    watch_id: str
    goal_id: str
    mode: str = "balanced"
    frequency: str = "daily"
    budget: dict[str, Any] = field(default_factory=dict)
    target_score: int = 100
    plateau_rounds: int = 3
    stop_rules: dict[str, Any] = field(default_factory=dict)
    provider_preferences: list[str] = field(default_factory=list)
    success_threshold: int = 100

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "GoalWatch":
        return cls(
            watch_id=str(
                payload.get("watch_id") or payload.get("goal_id") or "watch"
            ).strip(),
            goal_id=str(payload.get("goal_id") or "").strip(),
            mode=str(payload.get("mode") or "balanced").strip(),
            frequency=str(payload.get("frequency") or "daily").strip(),
            budget=dict(payload.get("budget") or {}),
            target_score=int(payload.get("target_score", 100) or 100),
            plateau_rounds=int(payload.get("plateau_rounds", 3) or 3),
            stop_rules=dict(payload.get("stop_rules") or {}),
            provider_preferences=[
                str(item).strip()
                for item in list(payload.get("provider_preferences") or [])
                if str(item).strip()
            ],
            success_threshold=int(
                payload.get("success_threshold", payload.get("target_score", 100))
                or 100
            ),
        )
