import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace


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

    def test_build_capability_report_tracks_runtime_availability(self):
        catalog = {
            "sources": [
                {
                    "name": "exa",
                    "kind": "provider",
                    "runtime_enabled": True,
                    "tier": 0,
                    "backend": "mcporter",
                    "check": "exa_mcporter",
                },
                {
                    "name": "alphaxiv_mcp",
                    "kind": "research_source",
                    "runtime_enabled": False,
                    "tier": 1,
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


if __name__ == "__main__":
    unittest.main()
