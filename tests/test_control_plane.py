import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import control_plane as cp


class ControlPlaneTests(unittest.TestCase):
    def test_control_plane_merges_capability_and_experience(self):
        catalog = {
            "sources": [
                {
                    "name": "exa",
                    "kind": "provider",
                    "family": "exa",
                    "runtime_enabled": True,
                    "backend": "mcporter",
                },
                {
                    "name": "twitter_xreach",
                    "kind": "provider",
                    "family": "twitter",
                    "runtime_enabled": True,
                    "backend": "xreach",
                },
                {
                    "name": "alphaxiv_mcp",
                    "kind": "research_source",
                    "family": "papers",
                    "runtime_enabled": False,
                    "backend": "Claude MCP SSE",
                },
            ]
        }
        capability_report = {
            "sources": {
                "exa": {
                    "status": "ok",
                    "available": True,
                    "runtime_enabled": True,
                    "message": "ready",
                },
                "twitter_xreach": {
                    "status": "off",
                    "available": False,
                    "runtime_enabled": True,
                    "message": "not authenticated",
                },
                "alphaxiv_mcp": {
                    "status": "ok",
                    "available": True,
                    "runtime_enabled": False,
                    "message": "reachable",
                },
            }
        }
        experience_policy = {
            "aspects": {
                "search": {
                    "providers": {
                        "exa": {"status": "preferred", "reason": "strong output"},
                        "twitter_xreach": {"status": "active", "reason": "neutral"},
                    },
                    "query_families": {
                        "mcp": {
                            "preferred_providers": ["exa"],
                            "cooldown_providers": [],
                        }
                    },
                }
            }
        }

        with patch("control_plane.load_source_catalog", return_value=catalog):
            payload = cp.build_control_plane(
                target_spec="Find MCP material",
                capability_report=capability_report,
                experience_policy=experience_policy,
                run_id="2026-03-24-daily-test",
            )

        self.assertEqual(payload["runtime"]["top_providers"], ["exa"])
        self.assertIn("twitter_xreach", payload["runtime"]["skipped_providers"])
        self.assertEqual(payload["query_families"][0]["name"], "mcp")
        self.assertEqual(payload["research_sources"][0]["name"], "alphaxiv_mcp")


if __name__ == "__main__":
    unittest.main()
