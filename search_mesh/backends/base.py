"""Base backend contracts for search mesh routing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from search_mesh.models import SearchHitBatch


class SearchBackend(Protocol):
    """Minimal backend contract for provider dispatch."""

    provider_names: tuple[str, ...]

    def search(self, platform: dict[str, Any], query: str, *, query_family: str = "unknown") -> SearchHitBatch:
        """Execute a search for a single configured provider."""


class SearchProvider:
    """Registry-facing provider contract."""

    provider_names: tuple[str, ...] = ()
    roles: set[str] = set()
    capabilities: dict[str, Any] = {}
    supports_cross_verification: bool = False
    supports_acquisition_hints: bool = False

    def transform_query(self, provider_name: str, query: str, context: dict[str, Any] | None = None) -> str:
        return str(query or "").strip()

    def search(self, platform: dict[str, Any], query: str, *, query_family: str = "unknown") -> SearchHitBatch:
        raise NotImplementedError


def quote_entities(query: str, entities: list[str] | None = None) -> str:
    updated = str(query or "").strip()
    for entity in list(entities or []):
        clean = str(entity or "").strip()
        if not clean or clean.startswith('"') or clean not in updated:
            continue
        updated = updated.replace(clean, f'"{clean}"')
    return updated


def extract_entities(query: str) -> list[str]:
    text = str(query or "").strip()
    entities: list[str] = []
    for match in re.findall(r"\b[A-Z][A-Za-z0-9_\-]+(?:\s+[A-Z][A-Za-z0-9_\-]+)*\b", text):
        clean = str(match or "").strip()
        if clean and clean not in entities:
            entities.append(clean)
    return entities


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
