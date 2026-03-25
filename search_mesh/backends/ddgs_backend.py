"""ddgs backend wrapper."""

from __future__ import annotations

from engine import PlatformConnector
from .base import legacy_results_to_batch


class DDGSBackend:
    provider_names = ("ddgs",)

    def search(self, platform: dict[str, Any], query: str, *, query_family: str = "unknown"):
        outcome = PlatformConnector._ddgs(platform, query)
        return legacy_results_to_batch(
            str(platform.get("name") or "ddgs"),
            query,
            list(outcome.results or []),
            backend="ddgs",
            query_family=query_family,
            error_alias=str(outcome.error_alias or ""),
        )
