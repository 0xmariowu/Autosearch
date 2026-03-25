"""Base backend contracts for search mesh routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from search_mesh.models import SearchHitBatch


class SearchBackend(Protocol):
    """Minimal backend contract for provider dispatch."""

    provider_names: tuple[str, ...]

    def search(self, platform: dict[str, Any], query: str, *, query_family: str = "unknown") -> SearchHitBatch:
        """Execute a search for a single configured provider."""


@dataclass(frozen=True)
class BackendRoute:
    """Resolved backend route for a provider name."""

    provider: str
    backend: SearchBackend


def legacy_results_to_batch(
    provider: str,
    query: str,
    results: list[Any] | None = None,
    *,
    backend: str = "",
    query_family: str = "unknown",
    error_alias: str = "",
) -> SearchHitBatch:
    items: list[dict[str, Any]] = []
    for result in list(results or []):
        items.append(
            {
                "title": str(getattr(result, "title", "") or ""),
                "url": str(getattr(result, "url", "") or ""),
                "body": str(getattr(result, "body", "") or ""),
                "source": str(getattr(result, "source", "") or provider),
                "eng": int(getattr(result, "eng", 0) or 0),
            }
        )
    return SearchHitBatch.from_hit_dicts(
        provider=str(provider or "").strip(),
        query=query,
        items=items,
        backend=backend or provider,
        query_family=query_family,
        error_alias=error_alias,
    )
