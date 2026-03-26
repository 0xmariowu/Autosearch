"""Explicit graph contracts for deep research execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GraphNode:
    node_id: str
    label: str
    node_type: str
    branch_type: str = ""
    branch_subgoal: str = ""
    priority: int = 0
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    source: str
    target: str
    kind: str = "branch"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchGraph:
    goal_id: str
    bundle_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    scheduler: dict[str, Any] = field(default_factory=dict)
    cross_verification: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "bundle_id": self.bundle_id,
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
            "scheduler": dict(self.scheduler),
            "cross_verification": dict(self.cross_verification),
        }
