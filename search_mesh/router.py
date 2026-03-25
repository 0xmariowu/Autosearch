"""Unified search mesh router."""

from __future__ import annotations

from typing import Any

from engine import PlatformConnector
from .models import SearchHitBatch
from .backends.base import BackendRoute
from .backends.ddgs_backend import DDGSBackend
from .backends.github_backend import GitHubBackend
from .backends.searxng_backend import SearXNGBackend
from .backends.web_backend import WebBackend


_BACKENDS = [
    SearXNGBackend(),
    DDGSBackend(),
    GitHubBackend(),
    WebBackend(),
]


def backend_for_provider(name: str):
    provider = str(name or "").strip()
    for backend in _BACKENDS:
        if provider in getattr(backend, "provider_names", ()):
            return backend
    return None


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
) -> SearchHitBatch:
    name = str(platform.get("name") or "").strip()
    route = route_for_provider(name)
    if route is None:
        outcome = PlatformConnector.search(platform, query)
        return SearchHitBatch.from_platform_outcome(
            outcome,
            query=query,
            backend=name or "platform_connector",
            query_family=query_family,
        )
    outcome = route.backend.search(dict(platform), query)
    return SearchHitBatch.from_platform_outcome(
        outcome,
        query=query,
        backend=name,
        query_family=query_family,
    )
