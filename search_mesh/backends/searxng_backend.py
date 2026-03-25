"""SearXNG backend wrapper."""

from __future__ import annotations

from engine import PlatformConnector
from .base import legacy_results_to_batch


class SearXNGBackend:
    provider_names = ("searxng",)

    def search(self, platform: dict[str, Any], query: str, *, query_family: str = "unknown"):
        outcome = PlatformConnector._searxng(platform, query)
        return legacy_results_to_batch(
            str(platform.get("name") or "searxng"),
            query,
            list(outcome.results or []),
            backend="searxng",
            query_family=query_family,
            error_alias=str(outcome.error_alias or ""),
        )
