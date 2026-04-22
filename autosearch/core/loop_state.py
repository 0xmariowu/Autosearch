"""Reflective search loop state — in-memory, per server process."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class LoopState:
    state_id: str
    visited_urls: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    bad_queries: list[str] = field(default_factory=list)
    best_evidence: list[dict] = field(default_factory=list)
    round_count: int = 0


# Module-level storage — in-memory, lost on server restart (intentional)
_LOOP_STATES: dict[str, LoopState] = {}


def init_loop() -> str:
    """Create a new loop state and return its state_id."""
    state_id = str(uuid.uuid4())
    _LOOP_STATES[state_id] = LoopState(state_id=state_id)
    return state_id


def update_loop(state_id: str, evidence: list[dict], query: str) -> dict:
    """Update loop state with new evidence.

    Extracts URLs from evidence dicts (checks 'url', 'link', 'source' keys).
    Adds only URLs not already in visited_urls. Increments round_count.

    Returns serialized state summary dict.
    """
    state = _LOOP_STATES[state_id]
    for item in evidence:
        url = item.get("url") or item.get("link") or item.get("source") or ""
        if url and url not in state.visited_urls:
            state.visited_urls.append(url)
    state.round_count += 1
    return {
        "state_id": state.state_id,
        "visited_urls": state.visited_urls,
        "gaps": state.gaps,
        "bad_queries": state.bad_queries,
        "round_count": state.round_count,
        "evidence_count": len(evidence),
    }


def get_gaps(state_id: str) -> list[str]:
    """Return current gap list for a loop state."""
    return _LOOP_STATES[state_id].gaps


def add_gap(state_id: str, gap: str) -> None:
    """Add a topic gap to the loop state."""
    _LOOP_STATES[state_id].gaps.append(gap)


def add_bad_query(state_id: str, query: str) -> None:
    """Record a query that returned poor results."""
    _LOOP_STATES[state_id].bad_queries.append(query)
