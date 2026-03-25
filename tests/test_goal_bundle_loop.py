import sys
import tempfile
import unittest
from types import SimpleNamespace
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

    def test_run_goal_bundle_loop_first_round_uses_candidate_plans_when_seed_queries_missing(self):
        goal_case = {
            "id": "goal-rubric-only",
            "providers": ["github_repos"],
            "rubric": [{"id": "judge", "weight": 20, "keywords": ["judge"]}],
            "target_score": 20,
        }
        fake_plan = {
            "label": "heuristic-primary",
            "queries": [{"text": "judge evaluator loop", "platforms": []}],
            "program_overrides": {},
        }
        fake_searcher = SimpleNamespace(
            initial_queries=lambda: [],
            candidate_plans=lambda **kwargs: [fake_plan],
        )
        fake_result = {
            "query": "judge evaluator loop",
            "query_spec": {"text": "judge evaluator loop", "platforms": []},
            "baseline_score": 12,
            "findings": [{"title": "judge evaluator loop", "url": "u", "source": "github_repos", "query": "judge evaluator loop"}],
        }
        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": "goal-rubric-only", "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher", return_value=fake_searcher), \
             patch.object(gbl, "load_accepted_program", return_value={"program_id": "seed-program", "queries": [], "sampling_policy": {}}), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(gbl, "_search_query", return_value=fake_result), \
             patch.object(gbl, "build_candidate_program", return_value={"program_id": "goal-rubric-only-r1-c1", "provider_mix": ["github_repos"], "sampling_policy": {}, "queries": fake_plan["queries"]}), \
             patch.object(gbl, "archive_candidate_program"), \
             patch.object(gbl, "save_population_snapshot"), \
             patch.object(gbl, "candidate_rank", side_effect=lambda item: int(item.get("score") or item["result"]["score"])), \
             patch.object(gbl, "evaluate_acceptance", return_value={"accepted": True, "candidate_score": 25, "reasons": ["score_gain"]}), \
             patch.object(gbl, "build_bundle", return_value=fake_result["findings"]), \
             patch.object(gbl, "bundle_metrics", return_value={"total_findings": 1, "new_unique_urls": 1, "novelty_ratio": 1.0, "source_diversity": 1.0, "source_concentration": 1.0, "query_concentration": 1.0}), \
             patch.object(gbl, "evaluate_goal_bundle", return_value={"score": 25, "dimension_scores": {"judge": 20}, "missing_dimensions": [], "matched_dimensions": ["judge"], "rationale": "ok", "judge": "heuristic-bundle"}), \
             patch.object(gbl, "save_accepted_program"):
            result = gbl.run_goal_bundle_loop(goal_case, max_rounds=1, plan_count_override=1, max_queries_override=1)
        self.assertEqual(result["rounds"][0]["selected_plan_label"], "heuristic-primary")
        self.assertEqual(result["rounds"][0]["queries"][0]["text"], "judge evaluator loop")


if __name__ == "__main__":
    unittest.main()
