"""Base backend contracts for search mesh routing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from search_mesh.models import SearchHitBatch


class SearchBackend(Protocol):
    """Minimal backend contract for provider dispatch."""

    provider_names: tuple[str, ...]

    def search(
        self, platform: dict[str, Any], query: str, *, query_family: str = "unknown"
    ) -> SearchHitBatch:
        """Execute a search for a single configured provider."""


class SearchProvider:
    """Registry-facing provider contract."""

    provider_names: tuple[str, ...] = ()
    provider_family: str = "generic"
    provider_families: dict[str, str] = {}
    roles: set[str] = set()
    capabilities: dict[str, Any] = {}
    supports_cross_verification: bool = False
    supports_acquisition_hints: bool = False

    def family_for(self, provider_name: str) -> str:
        name = str(provider_name or "").strip()
        return str(
            self.provider_families.get(name) or self.provider_family or "generic"
        ).strip()

    def transform_query(
        self, provider_name: str, query: str, context: dict[str, Any] | None = None
    ) -> str:
        return str(query or "").strip()

    def search(
        self, platform: dict[str, Any], query: str, *, query_family: str = "unknown"
    ) -> SearchHitBatch:
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
    for match in re.findall(
        r"\b[A-Z][A-Za-z0-9_\-]+(?:\s+[A-Z][A-Za-z0-9_\-]+)*\b", text
    ):
        clean = str(match or "").strip()
        if clean and clean not in entities:
            entities.append(clean)
    return entities


@dataclass(frozen=True)
class BackendRoute:
    """Resolved backend route for a provider name."""

    provider: str
    backend: SearchBackend
