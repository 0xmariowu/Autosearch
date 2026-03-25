"""Base backend contracts for search mesh routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from search_mesh.models import SearchHitBatch


class SearchBackend(Protocol):
    """Minimal backend contract for provider dispatch."""

    provider_names: tuple[str, ...]

    def search(self, platform: dict[str, Any], query: str):
        """Execute a search for a single configured provider."""


@dataclass(frozen=True)
class BackendRoute:
    """Resolved backend route for a provider name."""

    provider: str
    backend: SearchBackend
