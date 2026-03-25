import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine import PlatformSearchOutcome, SearchResult
from search_mesh.compat import to_legacy_search_results
from search_mesh.models import SearchHitBatch
from search_mesh.provider_policy import available_platforms, default_platform_config, goal_provider_names
from search_mesh.registry import (
    classify_query,
    get_provider,
    provider_names_for_classification,
    providers_for_role,
    registered_provider_names,
)
from search_mesh.router import route_for_provider, search_platform


class SearchMeshTests(unittest.TestCase):
    def test_search_hit_batch_builds_from_native_hit_dicts(self):
        batch = SearchHitBatch.from_hit_dicts(
            provider="searxng",
            query="agent eval harness",
            items=[
                {
                    "title": "Agent Eval Harness",
                    "url": "https://example.com/harness",
                    "body": "A practical agent evaluation harness",
                    "source": "searxng",
                    "eng": 7,
                }
            ],
            backend="searxng",
            query_family="evaluation",
        )
        self.assertEqual(batch.provider, "searxng")
        self.assertEqual(batch.backend, "searxng")
        self.assertEqual(batch.hits[0].query_family, "evaluation")
        self.assertEqual(batch.hits[0].score_hint, 7)

    def test_search_hit_batch_converts_to_legacy_results_at_compat_boundary(self):
        batch = SearchHitBatch.from_hit_dicts(
            provider="ddgs",
            query="research graph",
            items=[
                {
                    "title": "Research Graph",
                    "url": "https://example.com/graph",
                    "snippet": "recursive planning and execution",
                    "source": "ddgs",
                    "score_hint": 3,
                }
            ],
            backend="ddgs",
        )
        legacy = to_legacy_search_results(batch)
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0].title, "Research Graph")
        self.assertEqual(legacy[0].eng, 3)

    def test_goal_provider_names_injects_free_first_for_premium_breadth(self):
        names = goal_provider_names({"providers": ["exa", "github_repos"]})
        self.assertEqual(names, ["searxng", "ddgs", "exa", "github_repos"])

    def test_goal_provider_names_injects_free_breadth_for_specialized_only_goals(self):
        names = goal_provider_names({"providers": ["github_code", "github_repos"]})
        self.assertEqual(names, ["searxng", "ddgs", "github_code", "github_repos"])

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

    def test_provider_registry_exposes_registered_providers(self):
        names = registered_provider_names()
        self.assertIn("github_code", names)
        provider = get_provider("github_code")
        self.assertIsNotNone(provider)
        self.assertIn("code", provider.roles)
        self.assertEqual(provider.family_for("github_code"), "source_code")

    def test_provider_registry_filters_by_role(self):
        providers = providers_for_role("breadth")
        self.assertTrue(any("searxng" in provider.provider_names for provider in providers))

    def test_provider_registry_supports_classification_gating(self):
        self.assertEqual(classify_query("repo implementation patch", plan_role=""), "code")
        self.assertIn("github_code", provider_names_for_classification("code"))
        self.assertIn("reddit", provider_names_for_classification("discussion"))

    def test_search_platform_dispatches_to_wrapped_backend(self):
        with patch("search_mesh.backends.github_backend.PlatformConnector._github_code") as search:
            search.return_value = PlatformSearchOutcome(
                provider="github_code",
                results=[SearchResult(title="hit", url="https://example.com", source="github_code")],
            )
            outcome = search_platform({"name": "github_code", "limit": 5}, "release gate")
        self.assertIsInstance(outcome, SearchHitBatch)
        self.assertEqual(outcome.provider, "github_code")
        self.assertEqual(len(outcome.hits), 1)
        self.assertEqual(outcome.hits[0].title, "hit")

    def test_search_platform_applies_provider_query_transform(self):
        with patch("search_mesh.backends.github_backend.PlatformConnector._github_repos") as search:
            search.return_value = PlatformSearchOutcome(
                provider="github_repos",
                results=[],
            )
            search_platform({"name": "github_repos", "limit": 5}, "OpenManus agent runtime")
        forwarded_query = search.call_args.args[1]
        self.assertIn("stars:>20", forwarded_query)


if __name__ == "__main__":
    unittest.main()
