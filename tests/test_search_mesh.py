import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine import PlatformSearchOutcome, SearchResult
from search_mesh.provider_policy import available_platforms, default_platform_config, goal_provider_names
from search_mesh.router import route_for_provider, search_platform


class SearchMeshTests(unittest.TestCase):
    def test_goal_provider_names_injects_free_first_for_premium_breadth(self):
        names = goal_provider_names({"providers": ["exa", "github_repos"]})
        self.assertEqual(names, ["searxng", "ddgs", "exa", "github_repos"])

    def test_available_platforms_respects_capability_report(self):
        capability_report = {
            "sources": {
                "searxng": {"status": "ok", "available": True, "runtime_enabled": True, "tier": 0},
                "ddgs": {"status": "ok", "available": True, "runtime_enabled": True, "tier": 0},
                "exa": {"status": "off", "available": False, "runtime_enabled": True, "tier": 3},
            }
        }
        platforms = available_platforms({"providers": ["exa"]}, capability_report)
        self.assertEqual([item["name"] for item in platforms], ["searxng", "ddgs"])

    def test_default_platform_config_sets_expected_limits(self):
        self.assertEqual(default_platform_config("github_repos")["min_stars"], 20)
        self.assertEqual(default_platform_config("searxng")["limit"], 8)
        self.assertEqual(default_platform_config("twitter_xreach")["limit"], 10)

    def test_route_for_provider_finds_backend(self):
        route = route_for_provider("github_code")
        self.assertIsNotNone(route)
        self.assertEqual(route.provider, "github_code")

    def test_search_platform_dispatches_to_wrapped_backend(self):
        with patch("search_mesh.backends.github_backend.PlatformConnector._github_code") as search:
            search.return_value = PlatformSearchOutcome(
                provider="github_code",
                results=[SearchResult(title="hit", url="https://example.com", source="github_code")],
            )
            outcome = search_platform({"name": "github_code", "limit": 5}, "release gate")
        self.assertEqual(outcome.provider, "github_code")
        self.assertEqual(len(outcome.results), 1)


if __name__ == "__main__":
    unittest.main()
