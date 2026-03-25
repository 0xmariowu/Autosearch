"""SearXNG backend wrapper."""

from __future__ import annotations

from typing import Any

from engine import PlatformConnector, PlatformSearchOutcome


class SearXNGBackend:
    provider_names = ("searxng",)

    def search(self, platform: dict[str, Any], query: str) -> PlatformSearchOutcome:
        return PlatformConnector._searxng(platform, query)
