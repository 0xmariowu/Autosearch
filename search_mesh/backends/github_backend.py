"""GitHub backend wrappers."""

from __future__ import annotations

from typing import Any

from engine import PlatformConnector, PlatformSearchOutcome


class GitHubBackend:
    provider_names = ("github_repos", "github_issues", "github_code")

    def search(self, platform: dict[str, Any], query: str) -> PlatformSearchOutcome:
        name = str(platform.get("name") or "")
        if name == "github_repos":
            return PlatformConnector._github_repos(platform, query)
        if name == "github_code":
            return PlatformConnector._github_code(platform, query)
        return PlatformConnector._github_issues(platform, query)
