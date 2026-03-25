"""Unified search mesh router."""

from __future__ import annotations

from typing import Any

from engine import PlatformConnector
from .models import SearchHitBatch
from .backends.base import BackendRoute, legacy_results_to_batch
from .backends import register_builtin_providers
from .backends.base import extract_entities
from .registry import get_provider, registered_provider_names


def backend_for_provider(name: str):
    if not registered_provider_names():
        register_builtin_providers()
    return get_provider(str(name or "").strip())


def route_for_provider(name: str) -> BackendRoute | None:
    backend = backend_for_provider(name)
    if backend is None:
        return None
    return BackendRoute(provider=str(name or "").strip(), backend=backend)


def search_platform(
    platform: dict[str, Any],
    query: str,
    *,
    query_family: str = "unknown",
    context: dict[str, Any] | None = None,
) -> SearchHitBatch:
    name = str(platform.get("name") or "").strip()
    route = route_for_provider(name)
    if route is None:
        outcome = PlatformConnector.search(platform, query)
        return legacy_results_to_batch(
            str(getattr(outcome, "provider", "") or name or "platform_connector"),
            query,
            list(outcome.results or []),
            backend=name or "platform_connector",
            query_family=query_family,
            error_alias=str(outcome.error_alias or ""),
        )
    effective_context = {
        "query_family": query_family,
        "entities": extract_entities(query),
        **dict(context or {}),
    }
    transformed_query = route.backend.transform_query(name, query, effective_context)
    return route.backend.search(dict(platform), transformed_query, query_family=query_family)
