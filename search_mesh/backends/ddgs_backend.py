"""ddgs backend wrapper."""

from __future__ import annotations

from engine import PlatformConnector
from .base import SearchProvider, legacy_results_to_batch


class DDGSBackend(SearchProvider):
    provider_names = ("ddgs",)
    roles = {"breadth", "web"}
    capabilities = {"free_first": True, "query_transform": "generic_web"}
    supports_cross_verification = True
    supports_acquisition_hints = True

    def transform_query(self, provider_name: str, query: str, context: dict | None = None) -> str:
        return str(query or "").strip()

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
