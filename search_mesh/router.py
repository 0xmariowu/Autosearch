"""Unified search mesh router."""

from __future__ import annotations

from typing import Any

from engine import PlatformConnector, PlatformSearchOutcome
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


def search_platform(platform: dict[str, Any], query: str) -> PlatformSearchOutcome:
    name = str(platform.get("name") or "").strip()
    route = route_for_provider(name)
    if route is None:
        return PlatformConnector.search(platform, query)
    return route.backend.search(dict(platform), query)
