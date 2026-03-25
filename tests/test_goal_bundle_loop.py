import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import goal_bundle_loop as gbl


class GoalBundleLoopTests(unittest.TestCase):
    def test_harness_for_program_applies_sampling_policy_bundle_caps(self):
        harness = {
            "bundle_policy": {
                "per_query_cap": 5,
                "per_source_cap": 18,
                "per_domain_cap": 18,
            }
        }
        effective = gbl._harness_for_program(
            harness,
            {
                "sampling_policy": {
                    "bundle_per_query_cap": 2,
                    "bundle_per_source_cap": 9,
                }
            },
        )
        self.assertEqual(effective["bundle_policy"]["per_query_cap"], 2)
        self.assertEqual(effective["bundle_policy"]["per_source_cap"], 9)
        self.assertEqual(harness["bundle_policy"]["per_query_cap"], 5)

    def test_platforms_for_provider_mix_filters_defaults(self):
        platforms = [
            {"name": "github_repos", "limit": 5},
            {"name": "github_issues", "limit": 5},
            {"name": "huggingface_datasets", "limit": 5},
        ]
        filtered = gbl._platforms_for_provider_mix(platforms, ["github_issues", "huggingface_datasets"])
        self.assertEqual([item["name"] for item in filtered], ["github_issues", "huggingface_datasets"])

    def test_restrict_query_to_provider_mix_drops_disallowed_structured_platforms(self):
        query = {
            "text": "validation release gate",
            "platforms": [
                {"name": "github_code", "repo": "foo/bar", "query": "release gate"},
                {"name": "github_issues", "repo": "foo/bar", "query": "release gate"},
            ],
        }
        restricted = gbl._restrict_query_to_provider_mix(query, ["github_issues"])
        self.assertEqual([item["name"] for item in restricted["platforms"]], ["github_issues"])

    def test_accepted_queries_from_run_only_keeps_accepted_rounds(self):
        payload = {
            "warm_start": {
                "query_runs": [
                    {
                        "query_spec": {"text": "warm query", "platforms": []},
                    }
                ]
            },
            "rounds": [
                {
                    "accepted": True,
                    "queries": [
                        {"text": "query a", "platforms": [{"name": "github_repos", "query": "a"}]},
                        {"text": "query b", "platforms": []},
                    ],
                },
                {
                    "accepted": False,
                    "queries": [
                        {"text": "query c", "platforms": []},
                    ],
                },
                {
                    "accepted": True,
                    "queries": [
                        {"text": "query a", "platforms": [{"name": "github_repos", "query": "a"}]},
                    ],
                },
            ]
        }
        queries = gbl._accepted_queries_from_run(payload)
        self.assertEqual([item["text"] for item in queries], ["warm query", "query a", "query b"])

    def test_promote_compatible_archive_candidate_replays_and_saves_program(self):
        goal_case = {"id": "goal-x"}
        accepted_program = {"program_id": "seed-program", "queries": [{"text": "seed", "platforms": []}]}
        bundle_state = {
            "accepted_findings": [{"url": "https://a", "title": "a", "source": "github_repos", "query": "seed"}],
            "accepted_queries": [{"text": "seed", "platforms": []}],
            "score": 82,
            "judge": "openrouter:test",
            "dimension_scores": {"a": 14, "b": 15, "c": 17, "d": 18, "e": 18},
            "missing_dimensions": [],
            "matched_dimensions": ["a"],
            "rationale": "current",
        }
        archive_payload = {
            "candidate_program": {
                "program_id": "goal-x-r3-c2",
                "parent_program_id": "seed-program",
                "queries": [{"text": "new query", "platforms": []}],
            },
            "result": {
                "score": 82,
                "dimension_scores": {"a": 12, "b": 16, "c": 18, "d": 18, "e": 18},
                "harness_metrics": {
                    "total_findings": 36,
                    "new_unique_urls": 3,
                    "novelty_ratio": 0.08,
                    "source_diversity": 0.11,
                    "source_concentration": 0.5,
                    "query_concentration": 0.13,
                },
                "selection": {"current_score": 82},
            },
        }
        promoted_judge = {
            "score": 84,
            "dimension_scores": {"a": 16, "b": 16, "c": 18, "d": 18, "e": 18},
            "missing_dimensions": [],
            "matched_dimensions": ["a", "b"],
            "rationale": "promoted",
            "judge": "openrouter:test",
        }
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp) / "program-archive"
            archive_dir.mkdir(parents=True)
            archive_path = archive_dir / "goal-x-r3-c2.json"
            archive_path.write_text(__import__("json").dumps(archive_payload), encoding="utf-8")
            with patch.object(gbl, "runtime_paths", return_value={"program_archive": archive_dir}), \
                 patch.object(gbl, "_replay_queries", return_value=([{"query": "seed"}, {"query": "new query"}], bundle_state["accepted_findings"])), \
                 patch.object(gbl, "build_bundle", return_value=bundle_state["accepted_findings"]), \
                 patch.object(gbl, "evaluate_goal_bundle", return_value=promoted_judge), \
                 patch.object(gbl, "save_accepted_program") as save_mock:
                program, new_state, judge_result, promoted = gbl._promote_compatible_archive_candidate(
                    goal_case=goal_case,
                    accepted_program=accepted_program,
                    bundle_state=bundle_state,
                    harness={
                        "anti_cheat": {
                            "min_new_unique_urls": 1,
                            "min_novelty_ratio": 0.01,
                            "min_source_diversity": 0.15,
                            "max_source_concentration": 0.82,
                            "max_query_concentration": 0.7,
                        }
                    },
                    platforms=[],
                )
        self.assertEqual(program["program_id"], "goal-x-r3-c2")
        self.assertEqual([item["text"] for item in program["queries"]], ["seed", "new query"])
        self.assertEqual(new_state["score"], 84)
        self.assertEqual(judge_result["score"], 84)
        self.assertEqual(promoted["program_id"], "goal-x-r3-c2")
        save_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
