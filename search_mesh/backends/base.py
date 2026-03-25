"""Base backend contracts for search mesh routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from engine import PlatformSearchOutcome


class SearchBackend(Protocol):
    """Minimal backend contract for provider dispatch."""

    provider_names: tuple[str, ...]

    def search(self, platform: dict[str, Any], query: str) -> PlatformSearchOutcome:
        """Execute a search for a single configured provider."""


@dataclass(frozen=True)
class BackendRoute:
    """Resolved backend route for a provider name."""

    provider: str
    backend: SearchBackend
