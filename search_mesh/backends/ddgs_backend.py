"""ddgs backend wrapper."""

from __future__ import annotations

from typing import Any

from engine import PlatformConnector, PlatformSearchOutcome


class DDGSBackend:
    provider_names = ("ddgs",)

    def search(self, platform: dict[str, Any], query: str) -> PlatformSearchOutcome:
        return PlatformConnector._ddgs(platform, query)
