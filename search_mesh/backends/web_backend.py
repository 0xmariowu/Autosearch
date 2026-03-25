"""Generic web and auxiliary backend wrappers."""

from __future__ import annotations

from engine import PlatformConnector
from .base import legacy_results_to_batch


class WebBackend:
    provider_names = (
        "exa",
        "tavily",
        "twitter_xreach",
        "twitter_exa",
        "reddit_exa",
        "hn_exa",
        "huggingface_datasets",
        "reddit",
        "hn",
    )

    def search(self, platform: dict[str, Any], query: str, *, query_family: str = "unknown"):
        name = str(platform.get("name") or "")
        dispatch = {
            "exa": PlatformConnector._exa,
            "tavily": PlatformConnector._tavily,
            "twitter_xreach": PlatformConnector._twitter_xreach,
            "twitter_exa": PlatformConnector._twitter_exa,
            "reddit_exa": PlatformConnector._reddit_exa,
            "hn_exa": PlatformConnector._hn_exa,
            "huggingface_datasets": PlatformConnector._huggingface_datasets,
            "reddit": PlatformConnector._reddit_api,
            "hn": PlatformConnector._hn_algolia,
        }
        fn = dispatch.get(name)
        if not fn:
            outcome = PlatformConnector.search(platform, query)
        else:
            outcome = fn(platform, query)
        return legacy_results_to_batch(
            name or str(getattr(outcome, "provider", "") or "web"),
            query,
            list(outcome.results or []),
            backend=name or "web",
            query_family=query_family,
            error_alias=str(outcome.error_alias or ""),
        )
