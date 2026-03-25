import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import goal_runtime as gr


class GoalRuntimeTests(unittest.TestCase):
    def test_default_program_uses_seed_queries(self):
        program = gr.default_program(
            {
                "id": "g1",
                "seed_queries": ["a", {"text": "b", "platforms": []}],
                "topic_frontier": [{"id": "topic-a", "queries": ["frontier query"]}],
                "dimension_queries": {"gap_a": ["query a1"]},
                "explore_budget": 0.25,
                "exploit_budget": 0.75,
                "sampling_policy": {"bundle_per_query_cap": 4, "anchor_followups": False},
            },
            ["github_repos"],
        )
        self.assertEqual(program["program_id"], "seed-program")
        self.assertEqual([item["text"] for item in program["queries"]], ["a", "b"])
        self.assertEqual(program["topic_frontier"][0]["id"], "topic-a")
        self.assertEqual(program["query_templates"]["gap_a"], ["query a1"])
        self.assertEqual(program["dimension_strategies"]["gap_a"]["queries"][0]["text"], "query a1")
        self.assertEqual(program["round_roles"][0], "broad_recall")
        self.assertEqual(program["current_role"], "broad_recall")
        self.assertIn("search_backends", program)
        self.assertIn("backend_roles", program)
        self.assertIn("acquisition_policy", program)
        self.assertIn("evidence_policy", program)
        self.assertIn("repair_policy", program)
        self.assertIn("population_policy", program)
        self.assertEqual(program["explore_budget"], 0.25)
        self.assertEqual(program["exploit_budget"], 0.75)
        self.assertEqual(program["sampling_policy"]["bundle_per_query_cap"], 4)
        self.assertEqual(program["stop_rules"]["target_score"], 100)

    def test_build_candidate_program_applies_program_overrides(self):
        parent = gr.default_program(
            {
                "id": "g1",
                "seed_queries": ["seed"],
                "topic_frontier": [{"id": "topic-a", "queries": ["frontier query"]}],
            },
            ["github_repos"],
        )
        candidate = gr.build_candidate_program(
            goal_id="g1",
            parent_program=parent,
            label="frontier-topic-a",
            queries=[{"text": "next query", "platforms": []}],
            provider_mix=["github_repos"],
            round_index=1,
            candidate_index=1,
            program_overrides={
                "topic_frontier": [{"id": "topic-b", "queries": ["other frontier query"]}],
                "explore_budget": 0.7,
                "exploit_budget": 0.3,
                "sampling_policy": {"anchor_followups": False},
                "current_role": "dimension_repair",
                "search_backends": ["searxng", "ddgs"],
                "acquisition_policy": {"acquire_pages": True, "page_fetch_limit": 1},
                "evidence_policy": {"preferred_content_types": ["code"]},
                "repair_policy": {"target_weak_dimensions": 1},
                "population_policy": {"plan_count": 4, "max_queries": 2},
            },
        )
        self.assertEqual(candidate["topic_frontier"][0]["id"], "topic-b")
        self.assertEqual(candidate["explore_budget"], 0.7)
        self.assertEqual(candidate["exploit_budget"], 0.3)
        self.assertFalse(candidate["sampling_policy"]["anchor_followups"])
        self.assertEqual(candidate["current_role"], "dimension_repair")
        self.assertEqual(candidate["search_backends"], ["searxng", "ddgs"])
        self.assertTrue(candidate["acquisition_policy"]["acquire_pages"])
        self.assertEqual(candidate["evidence_policy"]["preferred_content_types"], ["code"])
        self.assertEqual(candidate["repair_policy"]["target_weak_dimensions"], 1)
        self.assertEqual(candidate["population_policy"]["plan_count"], 4)

    def test_ensure_harness_persists_default_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            with patch.object(gr, "GOAL_RUNTIME_ROOT", runtime_root):
                harness = gr.ensure_harness({"id": "goal-x"})
                self.assertEqual(harness["goal_id"], "goal-x")
                saved = gr.runtime_paths("goal-x")["harness"]
                self.assertTrue(saved.exists())

    def test_save_population_snapshot_writes_latest_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            with patch.object(gr, "GOAL_RUNTIME_ROOT", runtime_root):
                paths = gr.save_population_snapshot(
                    "goal-x",
                    2,
                    [{"program_id": "p1", "score": 88}],
                )
                self.assertTrue(paths["latest"].exists())
                self.assertTrue(paths["history"].exists())
                self.assertTrue(paths["latest_lineage"].exists())
                self.assertTrue(paths["lineage_history"].exists())
                payload = __import__("json").loads(paths["latest"].read_text(encoding="utf-8"))
                self.assertEqual(payload["round"], 2)
                self.assertEqual(payload["population"][0]["program_id"], "p1")
                lineage = __import__("json").loads(paths["latest_lineage"].read_text(encoding="utf-8"))
                self.assertEqual(lineage["summary"]["top_score"], 88)


if __name__ == "__main__":
    unittest.main()
