"""GitHub backend wrappers."""

from __future__ import annotations

from engine import PlatformConnector
from .base import legacy_results_to_batch


class GitHubBackend:
    provider_names = ("github_repos", "github_issues", "github_code")

    def search(self, platform: dict[str, Any], query: str, *, query_family: str = "unknown"):
        name = str(platform.get("name") or "")
        if name == "github_repos":
            outcome = PlatformConnector._github_repos(platform, query)
        elif name == "github_code":
            outcome = PlatformConnector._github_code(platform, query)
        else:
            outcome = PlatformConnector._github_issues(platform, query)
        return legacy_results_to_batch(
            name or "github_issues",
            query,
            list(outcome.results or []),
            backend=name or "github",
            query_family=query_family,
            error_alias=str(outcome.error_alias or ""),
        )
