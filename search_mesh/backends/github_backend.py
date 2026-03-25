"""GitHub backend wrappers."""

from __future__ import annotations

from engine import PlatformConnector
from .base import SearchProvider, extract_entities, quote_entities
from ..compat import batch_from_legacy_results


class GitHubBackend(SearchProvider):
    provider_names = ("github_repos", "github_issues", "github_code")
    provider_family = "code_host"
    provider_families = {
        "github_repos": "code_host",
        "github_issues": "discussion",
        "github_code": "source_code",
    }
    roles = {"code", "discussion", "verification"}
    capabilities = {"supports_query_qualifiers": True, "supports_code_search": True}
    supports_cross_verification = True
    supports_acquisition_hints = False

    def transform_query(self, provider_name: str, query: str, context: dict | None = None) -> str:
        q = str(query or "").strip()
        entities = list((context or {}).get("entities") or extract_entities(q))
        if provider_name == "github_repos" and "stars:" not in q:
            q = f"{q} stars:>20".strip()
        elif provider_name == "github_issues":
            q = quote_entities(q, entities)
        elif provider_name == "github_code":
            q = quote_entities(q, entities)
        return q

    def search(self, platform: dict[str, Any], query: str, *, query_family: str = "unknown"):
        name = str(platform.get("name") or "")
        if name == "github_repos":
            outcome = PlatformConnector._github_repos(platform, query)
        elif name == "github_code":
            outcome = PlatformConnector._github_code(platform, query)
        else:
            outcome = PlatformConnector._github_issues(platform, query)
        return batch_from_legacy_results(
            name or "github_issues",
            query,
            list(outcome.results or []),
            backend=name or "github",
            query_family=query_family,
            error_alias=str(outcome.error_alias or ""),
        )
