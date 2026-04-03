"""Artifacts for explicit search-read-reason deep loop execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DeepLoopStep:
    kind: str
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeepLoopState:
    mode: str
    steps: list[DeepLoopStep] = field(default_factory=list)
    saturated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "steps": [item.to_dict() for item in self.steps],
            "saturated": self.saturated,
        }


def build_deep_loop_state(
    *,
    mode: str,
    graph_plan: dict[str, Any] | None,
    bundle: list[dict[str, Any]],
    judge_result: dict[str, Any],
) -> DeepLoopState:
    plan = dict(graph_plan or {})
    explicit_steps = list(plan.get("deep_steps") or [])
    if explicit_steps:
        return DeepLoopState(
            mode=str(mode or "balanced"),
            steps=[
                DeepLoopStep(
                    kind=str(item.get("kind") or ""),
                    summary=str(item.get("summary") or ""),
                    metadata=dict(item.get("metadata") or {}),
                )
                for item in explicit_steps
            ],
            saturated=not bool(judge_result.get("missing_dimensions")),
        )
    query_runs = list(plan.get("query_runs") or [])
    decision = dict(plan.get("decision") or {})
    queries = [
        str(item.get("query") or item.get("query_spec", {}).get("text") or "").strip()
        for item in query_runs
        if str(
            item.get("query") or item.get("query_spec", {}).get("text") or ""
        ).strip()
    ]
    read_count = sum(
        1
        for item in list(bundle or [])
        if bool(item.get("extract"))
        or bool(item.get("body"))
        or bool(item.get("clean_markdown"))
    )
    missing = [
        str(item).strip()
        for item in list(judge_result.get("missing_dimensions") or [])
        if str(item).strip()
    ]
    steps = [
        DeepLoopStep(
            kind="search",
            summary=f"searched {len(query_runs)} queries",
            metadata={
                "queries": queries[:8],
                "cross_verify": bool(decision.get("cross_verify")),
            },
        ),
        DeepLoopStep(
            kind="read",
            summary=f"read {read_count} evidence records",
            metadata={"bundle_size": len(bundle)},
        ),
        DeepLoopStep(
            kind="reason",
            summary="reasoned over evidence gaps",
            metadata={"missing_dimensions": missing[:6]},
        ),
    ]
    return DeepLoopState(
        mode=str(mode or "balanced"),
        steps=steps,
        saturated=not bool(missing),
    )
