"""Decision objects for think/act research execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SearchDecision:
    """Planner-side decision that the executor can apply without re-reasoning."""

    role: str
    mode: str
    provider_mix: list[str] = field(default_factory=list)
    search_backends: list[str] = field(default_factory=list)
    backend_roles: dict[str, list[str]] = field(default_factory=dict)
    sampling_policy: dict[str, Any] = field(default_factory=dict)
    acquisition_policy: dict[str, Any] = field(default_factory=dict)
    evidence_policy: dict[str, Any] = field(default_factory=dict)
    cross_verify: bool = False
    cross_verification_queries: list[dict[str, Any]] = field(default_factory=list)
    stop_if_saturated: bool = False
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
