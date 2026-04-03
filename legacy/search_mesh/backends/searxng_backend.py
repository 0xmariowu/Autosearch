"""SearXNG backend wrapper."""

from __future__ import annotations
from typing import Any

from engine import PlatformConnector
from .base import SearchProvider
from ..compat import batch_from_legacy_results


class SearXNGBackend(SearchProvider):
    provider_names = ("searxng",)
    provider_family = "web_search"
    roles = {"breadth", "web"}
    capabilities = {"free_first": True, "query_transform": "generic_web"}
    supports_cross_verification = True
    supports_acquisition_hints = True

    def transform_query(
        self, provider_name: str, query: str, context: dict | None = None
    ) -> str:
        return str(query or "").strip()

    def search(
        self, platform: dict[str, Any], query: str, *, query_family: str = "unknown"
    ):
        outcome = PlatformConnector._searxng(platform, query)
        return batch_from_legacy_results(
            str(platform.get("name") or "searxng"),
            query,
            list(outcome.results or []),
            backend="searxng",
            query_family=query_family,
            error_alias=str(outcome.error_alias or ""),
        )
