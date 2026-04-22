"""Graph-search-plan: represent a research plan as a DAG and return parallel batches."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubTask:
    id: str
    description: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class SearchGraph:
    nodes: list[SubTask] = field(default_factory=list)

    def node_ids(self) -> set[str]:
        return {node.id for node in self.nodes}


def get_parallel_batches(graph: SearchGraph) -> list[list[str]]:
    """Topological sort returning groups of node IDs that can run in parallel.

    Each batch contains nodes whose dependencies are all satisfied by
    previous batches. Nodes with no dependencies are in the first batch.

    Raises ValueError for unknown dependency references or cycles.
    """
    node_ids = graph.node_ids()
    deps: dict[str, set[str]] = {}
    for node in graph.nodes:
        unknown = [d for d in node.depends_on if d not in node_ids]
        if unknown:
            raise ValueError(f"node '{node.id}' depends on unknown nodes: {unknown}")
        deps[node.id] = set(node.depends_on)

    batches: list[list[str]] = []
    completed: set[str] = set()

    remaining = dict(deps)
    while remaining:
        ready = [nid for nid, d in remaining.items() if d <= completed]
        if not ready:
            raise ValueError(f"cycle detected among nodes: {list(remaining.keys())}")
        batch = sorted(ready)
        batches.append(batch)
        completed.update(batch)
        for nid in batch:
            del remaining[nid]

    return batches


def graph_from_dicts(subtasks: list[dict]) -> SearchGraph:
    """Build a SearchGraph from a list of dicts with keys: id, description, depends_on."""
    nodes = [
        SubTask(
            id=str(item["id"]),
            description=str(item.get("description") or ""),
            depends_on=[str(d) for d in (item.get("depends_on") or [])],
        )
        for item in subtasks
    ]
    return SearchGraph(nodes=nodes)
