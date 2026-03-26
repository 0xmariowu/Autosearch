"""Generic web and auxiliary backend wrappers."""

from __future__ import annotations

from engine import PlatformConnector
from .base import SearchProvider, extract_entities, quote_entities
from ..compat import batch_from_legacy_results


class WebBackend(SearchProvider):
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
    provider_family = "web_search"
    provider_families = {
        "exa": "web_search",
        "tavily": "web_search",
        "twitter_xreach": "social",
        "twitter_exa": "social",
        "reddit_exa": "discussion",
        "hn_exa": "discussion",
        "huggingface_datasets": "dataset",
        "reddit": "discussion",
        "hn": "discussion",
    }
    roles = {"web", "discussion", "academic", "verification"}
    capabilities = {"supports_query_transform": True}
    supports_cross_verification = True
    supports_acquisition_hints = True

    def transform_query(
        self, provider_name: str, query: str, context: dict | None = None
    ) -> str:
        q = str(query or "").strip()
        entities = list((context or {}).get("entities") or extract_entities(q))
        if provider_name in {"reddit_exa", "reddit"} and "sort:relevance" not in q:
            q = f"{q} sort:relevance".strip()
        if provider_name in {"hn_exa", "hn"}:
            q = quote_entities(q, entities or [q] if q and " " in q else entities)
        return q

    def search(
        self, platform: dict[str, Any], query: str, *, query_family: str = "unknown"
    ):
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
        return batch_from_legacy_results(
            name or str(getattr(outcome, "provider", "") or "web"),
            query,
            list(outcome.results or []),
            backend=name or "web",
            query_family=query_family,
            error_alias=str(outcome.error_alias or ""),
        )
