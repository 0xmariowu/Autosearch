"""Reusable deep-research report packets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RouteableResearchPacket:
    packet_id: str
    goal_id: str
    query: str
    mode: str
    score: int
    citations: list[str] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    contradictions: dict[str, Any] = field(default_factory=dict)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_research_packet(
    *,
    goal_case: dict[str, Any],
    bundle: list[dict[str, Any]],
    judge_result: dict[str, Any],
    cross_verification: dict[str, Any] | None = None,
    next_actions: list[dict[str, Any]] | None = None,
) -> RouteableResearchPacket:
    cross = dict(cross_verification or {})
    packet_id = f"{str(goal_case.get('id') or 'goal')}:{int(judge_result.get('score', 0) or 0)}:{len(bundle)}"
    query = " ".join(
        part
        for part in (
            str(goal_case.get("problem") or "").strip(),
            str(goal_case.get("title") or "").strip(),
        )
        if part
    ).strip()
    claims = list(cross.get("claim_alignment") or [])[:12]
    evidence_refs = [
        {
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "source": str(item.get("source") or ""),
            "content_type": str(item.get("content_type") or ""),
        }
        for item in list(bundle or [])[:12]
    ]
    return RouteableResearchPacket(
        packet_id=packet_id,
        goal_id=str(goal_case.get("id") or ""),
        query=query,
        mode=str(goal_case.get("mode") or "balanced"),
        score=int(judge_result.get("score", 0) or 0),
        citations=[
            str(item.get("url") or "")
            for item in list(bundle or [])
            if str(item.get("url") or "")
        ][:20],
        claims=claims,
        contradictions={
            "consensus_strength": str(cross.get("consensus_strength") or ""),
            "contradiction_detected": bool(cross.get("contradiction_detected", False)),
            "contradiction_clusters": list(cross.get("contradiction_clusters") or []),
            "source_dispute_map": dict(cross.get("source_dispute_map") or {}),
        },
        next_actions=list(next_actions or []),
        evidence_refs=evidence_refs,
    )
