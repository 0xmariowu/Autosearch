import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import project_experience as pe


class ProjectExperienceTests(unittest.TestCase):
    def test_build_policy_respects_thresholds_and_alias_errors(self):
        events = []
        for idx in range(8):
            run_id = f"2026-03-24-daily-{idx:02d}"
            events.append(
                pe.build_search_experience_event(
                    run_id=run_id,
                    provider="exa",
                    query_family="coding-agent",
                    attempts=1,
                    results=5,
                    new_urls=1,
                    errors=0,
                    timestamp=f"2026-03-24T06:{idx:02d}:00+08:00",
                )
            )
            events.append(
                pe.build_search_experience_event(
                    run_id=run_id,
                    provider="xreach_auth_error",
                    query_family="coding-agent",
                    attempts=1,
                    results=0,
                    new_urls=0,
                    errors=1,
                    timestamp=f"2026-03-24T06:{idx:02d}:30+08:00",
                )
            )

        index = pe.build_project_experience_index(events)
        policy = pe.build_project_experience_policy(index)
        search_policy = policy["aspects"]["search"]

        self.assertEqual(search_policy["providers"]["exa"]["status"], "preferred")
        self.assertEqual(
            search_policy["providers"]["xreach_auth_error"]["status"], "cooldown"
        )
        self.assertEqual(
            search_policy["providers"]["twitter_xreach"]["status"], "cooldown"
        )
        self.assertIn(
            "exa",
            search_policy["query_families"]["coding-agent"]["preferred_providers"],
        )
        self.assertIn(
            "twitter_xreach",
            search_policy["query_families"]["coding-agent"]["cooldown_providers"],
        )

    def test_small_sample_stays_active(self):
        events = [
            pe.build_search_experience_event(
                run_id=f"2026-03-24-daily-{idx:02d}",
                provider="github_repos",
                query_family="mcp",
                attempts=1,
                results=5,
                new_urls=1,
                errors=0,
                timestamp=f"2026-03-24T07:{idx:02d}:00+08:00",
            )
            for idx in range(7)
        ]
        index = pe.build_project_experience_index(events)
        policy = pe.build_project_experience_policy(index)
        decision = pe.get_provider_decision(policy, "github_repos", "mcp")

        self.assertEqual(
            policy["aspects"]["search"]["providers"]["github_repos"]["status"], "active"
        )
        self.assertFalse(decision["should_skip"])
        self.assertEqual(decision["status"], "active")

    def test_github_auth_error_cools_down_both_github_providers(self):
        events = [
            pe.build_search_experience_event(
                run_id=f"2026-03-24-daily-{idx:02d}",
                provider="gh_auth_error",
                query_family="mcp",
                attempts=1,
                results=0,
                new_urls=0,
                errors=1,
                timestamp=f"2026-03-24T08:{idx:02d}:00+08:00",
            )
            for idx in range(8)
        ]
        index = pe.build_project_experience_index(events)
        policy = pe.build_project_experience_policy(index)
        search_policy = policy["aspects"]["search"]["providers"]

        self.assertEqual(search_policy["gh_auth_error"]["status"], "cooldown")
        self.assertEqual(search_policy["github_repos"]["status"], "cooldown")
        self.assertEqual(search_policy["github_issues"]["status"], "cooldown")


if __name__ == "__main__":
    unittest.main()
