import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import types


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine import Engine, EngineConfig, PlatformConnector, PlatformSearchOutcome, SearchResult
import source_capability as sc


class SourceCapabilityTests(unittest.TestCase):
    def test_github_code_search_parses_text_matches(self):
        payload = """
        [
          {
            "path": "docs/release.md",
            "url": "https://github.com/example/project/blob/main/docs/release.md",
            "repository": {"nameWithOwner": "example/project", "url": "https://github.com/example/project"},
            "textMatches": [
              {"fragment": "Use a fail-closed release gate after validation."}
            ]
          }
        ]
        """
        with patch("engine.subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout=payload, stderr="")
            result = PlatformConnector._github_code({"name": "github_code", "limit": 5}, "fail-closed")
        self.assertEqual(result.provider, "github_code")
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].title, "example/project:docs/release.md")
        self.assertIn("fail-closed release gate", result.results[0].body)

    def test_tavily_search_parses_results(self):
        payload = {
            "results": [
                {
                    "title": "Provider doctor patterns",
                    "url": "https://example.com/provider-doctor",
                    "content": "doctor report and runtime skip implementation",
                    "score": 0.82,
                }
            ]
        }
        class FakeResponse:
            def read(self):
                return __import__("json").dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch.dict("os.environ", {"TAVILY_API_KEY": "tvly-demo-key-1234567890"}, clear=False), \
             patch("engine.urllib.request.urlopen", return_value=FakeResponse()):
            result = PlatformConnector._tavily({"name": "tavily", "limit": 5}, "provider doctor")
        self.assertEqual(result.provider, "tavily")
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].url, "https://example.com/provider-doctor")

    def test_searxng_search_parses_results(self):
        payload = {
            "results": [
                {
                    "title": "Search orchestration with citations",
                    "url": "https://example.com/orchestration",
                    "content": "planner executor synthesizer with citations",
                }
            ]
        }

        class FakeResponse:
            status = 200

            def read(self):
                return __import__("json").dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("engine.urllib.request.urlopen", return_value=FakeResponse()):
            result = PlatformConnector._searxng({"name": "searxng", "limit": 5}, "search orchestration")

        self.assertEqual(result.provider, "searxng")
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].url, "https://example.com/orchestration")

    def test_ddgs_search_parses_results(self):
        class FakeDDGS:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def text(self, query, max_results=5, backend="auto"):
                return [
                    {
                        "title": "Local meta search",
                        "href": "https://example.com/ddgs-result",
                        "body": "ddgs aggregates multiple public engines",
                    }
                ]

        fake_module = types.SimpleNamespace(DDGS=FakeDDGS)
        with patch.dict(sys.modules, {"ddgs": fake_module}):
            result = PlatformConnector._ddgs({"name": "ddgs", "limit": 5}, "meta search")

        self.assertEqual(result.provider, "ddgs")
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].url, "https://example.com/ddgs-result")

    def test_tavily_capability_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            status = sc.check_source({
                "name": "tavily",
                "kind": "provider",
                "runtime_enabled": True,
                "tier": 0,
                "backend": "Tavily Search API",
                "check": "tavily_api",
            })
        self.assertFalse(status["available"])

    def test_ddgs_capability_requires_installed_package(self):
        with patch("source_capability.importlib.util.find_spec", return_value=None):
            status = sc.check_source({
                "name": "ddgs",
                "kind": "provider",
                "runtime_enabled": True,
                "tier": 0,
                "backend": "Local ddgs Python package",
                "check": "ddgs_local",
            })
        self.assertFalse(status["available"])

    def test_searxng_capability_reports_reachable_endpoint(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch.dict("os.environ", {"SEARXNG_URL": "http://127.0.0.1:8888"}), \
             patch("source_capability.urllib.request.urlopen", return_value=FakeResponse()):
            status = sc.check_source({
                "name": "searxng",
                "kind": "provider",
                "runtime_enabled": True,
                "tier": 0,
                "backend": "Local SearXNG HTTP",
                "check": "searxng_http",
            })
        self.assertTrue(status["available"])
        self.assertEqual(status["status"], "ok")

    def test_build_capability_report_tracks_runtime_availability(self):
        catalog = {
            "sources": [
                {
                    "name": "exa",
                    "kind": "provider",
                    "runtime_enabled": True,
                    "tier": "premium_fallback",
                    "backend": "mcporter",
                    "check": "exa_mcporter",
                },
                {
                    "name": "alphaxiv_mcp",
                    "kind": "research_source",
                    "runtime_enabled": False,
                    "tier": "specialized_free",
                    "backend": "Claude MCP SSE",
                    "check": "alphaxiv_mcp",
                },
            ]
        }

        def checker(source):
            if source["name"] == "exa":
                return {
                    "status": "ok",
                    "available": True,
                    "runtime_enabled": True,
                    "message": "ready",
                }
            return {
                "status": "ok",
                "available": True,
                "runtime_enabled": False,
                "message": "optional",
            }

        report = sc.build_source_capability_report(catalog, checker=checker)
        self.assertEqual(report["summary"]["runtime_sources"], ["exa"])
        self.assertEqual(report["summary"]["runtime_available"], ["exa"])
        self.assertEqual(report["summary"]["premium_available"], ["exa"])
        self.assertEqual(report["summary"]["runtime_unavailable"], [])
        self.assertTrue(sc.get_source_decision(report, "alphaxiv_mcp")["should_skip"])

    def test_engine_skips_unavailable_provider_from_capability_report(self):
        config = EngineConfig(
            genes={"entity": ["MCP"], "object": ["server"], "context": ["2026"]},
            platforms=[{"name": "twitter_xreach"}, {"name": "exa"}],
            target_spec="test",
            capability_report={
                "sources": {
                    "twitter_xreach": {
                        "status": "off",
                        "available": False,
                        "runtime_enabled": True,
                        "message": "not authenticated",
                    },
                    "exa": {
                        "status": "ok",
                        "available": True,
                        "runtime_enabled": True,
                        "message": "ready",
                    },
                }
            },
        )
        engine = Engine(config, REPO_ROOT)

        with patch("engine.PlatformConnector.search") as search:
            search.return_value = PlatformSearchOutcome(
                provider="exa",
                results=[SearchResult(title="A", url="https://example.com", source="exa")],
            )
            results = engine._search_all_platforms("paper search", "mcp")

        self.assertEqual(len(results), 1)
        self.assertEqual(search.call_count, 1)
        platform_arg = search.call_args[0][0]
        self.assertEqual(platform_arg["name"], "exa")

    def test_source_decision_priority_prefers_lower_tier_when_available(self):
        report = {
            "sources": {
                "searxng": {"status": "ok", "available": True, "runtime_enabled": True, "tier": "free_default"},
                "exa": {"status": "ok", "available": True, "runtime_enabled": True, "tier": "premium_fallback"},
            }
        }
        searxng = sc.get_source_decision(report, "searxng")
        exa = sc.get_source_decision(report, "exa")
        self.assertLess(searxng["priority"], exa["priority"])

    def test_format_report_surfaces_free_path_before_premium_fallback(self):
        report = {
            "sources": {
                "searxng": {"status": "ok", "available": True, "runtime_enabled": True, "tier": "free_default", "message": "ready"},
                "github_repos": {"status": "ok", "available": True, "runtime_enabled": True, "tier": "specialized_free", "message": "ready"},
                "exa": {"status": "ok", "available": True, "runtime_enabled": True, "tier": "premium_fallback", "message": "ready"},
            },
            "summary": {
                "ok": 3,
                "warn": 0,
                "off": 0,
                "error": 0,
                "runtime_unavailable": [],
                "free_active": ["searxng"],
                "specialized_active": ["github_repos"],
                "premium_available": ["exa"],
            },
        }
        text = sc.format_source_capability_report(report)
        self.assertIn("Active free-first path: searxng", text)
        self.assertIn("Active specialized free providers: github_repos", text)
        self.assertIn("Premium fallback available: exa", text)


if __name__ == "__main__":
    unittest.main()
