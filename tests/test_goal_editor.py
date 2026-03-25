import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_editor import GoalSearcher, HeuristicGoalSearcher, _normalize_query_spec
from goal_judge import evaluate_goal_bundle


class GoalEditorTests(unittest.TestCase):
    def test_editor_uses_missing_dimensions_to_choose_queries(self):
        goal_case = {
            "seed_queries": ["seed a"],
            "refinement_terms": ["issue"],
            "dimension_queries": {
                "gap_a": ["query a1", "query a2"],
                "gap_b": ["query b1"],
            },
        }
        editor = HeuristicGoalSearcher(goal_case)
        next_queries = editor.next_queries(
            bundle_state={"accepted_findings": []},
            judge_result={"missing_dimensions": ["gap_b", "gap_a"]},
            tried_queries={"query b1::[]"},
        )
        self.assertEqual(next_queries[0]["text"], "query a1")
        self.assertEqual(next_queries[1]["text"], "query a2")

    def test_editor_keeps_scanning_later_templates_when_first_slot_is_exhausted(self):
        goal_case = {
            "seed_queries": ["seed a"],
            "dimension_queries": {
                "gap_a": ["query a1", "query a2"],
                "gap_b": ["query b1", "query b2"],
            },
        }
        editor = HeuristicGoalSearcher(goal_case)
        next_queries = editor.next_queries(
            bundle_state={"accepted_findings": []},
            judge_result={"missing_dimensions": ["gap_a", "gap_b"]},
            tried_queries={"query a1::[]", "query b1::[]"},
            round_history=[{"accepted": False, "queries": [{"text": "query a1"}, {"text": "query b1"}]}],
            max_queries=2,
        )
        self.assertEqual([query["text"] for query in next_queries], ["query a2", "query b2"])

    def test_editor_preserves_structured_query_specs(self):
        goal_case = {
            "seed_queries": [
                {
                    "text": "validation",
                    "platforms": [{"name": "github_issues", "repo": "foo/bar", "limit": 5}],
                }
            ],
            "dimension_queries": {},
        }
        editor = HeuristicGoalSearcher(goal_case)
        initial = editor.initial_queries()
        self.assertEqual(initial[0]["text"], "validation")
        self.assertEqual(initial[0]["platforms"][0]["repo"], "foo/bar")

    def test_goal_director_returns_candidate_plans_without_llm(self):
        goal_case = {
            "seed_queries": ["seed a"],
            "dimension_queries": {
                "gap_a": ["query a1", "query a2"],
            },
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 0},
            judge_result={"missing_dimensions": ["gap_a"], "dimension_scores": {}},
            tried_queries=set(),
            available_providers=["github_issues"],
            plan_count=2,
            max_queries=2,
        )
        self.assertGreaterEqual(len(plans), 1)
        self.assertEqual(plans[0]["queries"][0]["text"], "query a1")
        self.assertIn("program_overrides", plans[0])

    def test_goal_director_uses_active_program_query_templates(self):
        goal_case = {
            "seed_queries": ["seed a"],
            "dimension_queries": {
                "gap_a": ["query a1"],
            },
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 0},
            judge_result={"missing_dimensions": ["gap_a"], "dimension_scores": {}},
            tried_queries=set(),
            available_providers=["github_issues"],
            active_program={"query_templates": {"gap_a": ["query override"]}},
            plan_count=1,
            max_queries=2,
        )
        self.assertEqual(plans[0]["queries"][0]["text"], "query override")
        self.assertEqual(
            plans[0]["program_overrides"]["query_templates"]["gap_a"][0]["text"],
            "query override",
        )

    def test_heuristic_editor_avoids_recent_failed_queries(self):
        goal_case = {
            "seed_queries": ["seed a"],
            "dimension_queries": {
                "gap_a": ["query a1", "query a2"],
                "gap_b": ["query b1"],
            },
        }
        editor = HeuristicGoalSearcher(goal_case)
        plans = editor.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 70},
            judge_result={"missing_dimensions": ["gap_a", "gap_b"], "dimension_scores": {"gap_a": 10, "gap_b": 12}},
            tried_queries=set(),
            available_providers=["github_issues"],
            round_history=[
                {
                    "round": 3,
                    "accepted": False,
                    "queries": [{"text": "query a1"}],
                }
            ],
            plan_count=3,
            max_queries=2,
        )
        flattened = [query["text"] for plan in plans for query in plan["queries"]]
        self.assertNotIn("query a1", flattened)
        self.assertIn("query a2", flattened)

    def test_bundle_judge_heuristic_scores_dimensions(self):
        goal_case = {
            "dimensions": [
                {"id": "direct", "weight": 20, "keywords": ["direct conversion", "before after"]},
                {"id": "validation", "weight": 20, "keywords": ["checklist", "contract"]},
            ]
        }
        findings = [
            {"title": "Direct conversion with before after code pairs", "url": "u1", "source": "exa"},
            {"title": "Validation checklist and contract for release gate", "url": "u2", "source": "exa"},
        ]
        result = evaluate_goal_bundle(goal_case, findings)
        self.assertGreaterEqual(result["score"], 20)
        self.assertIn("direct", result["dimension_scores"])
        self.assertIn("validation", result["dimension_scores"])

    def test_normalize_query_spec_rewrites_code_literal_platform_query(self):
        spec = _normalize_query_spec({
            "text": "fail closed release gate",
            "platforms": [
                {
                    "name": "github_code",
                    "query": "if not validation_success: raise Exception(\"Release gate failed\")",
                    "limit": 5,
                }
            ],
        })
        self.assertEqual(spec["platforms"][0]["query"], "fail closed release gate")

    def test_heuristic_searcher_can_generate_anchored_repo_queries(self):
        goal_case = {
            "dimensions": [
                {"id": "validation_release", "keywords": ["fail-closed", "validation report"]},
            ],
            "dimension_queries": {},
            "seed_queries": [],
        }
        searcher = HeuristicGoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={
                "accepted_findings": [
                    {
                        "title": "great-expectations/great_expectations",
                        "url": "https://github.com/great-expectations/great_expectations",
                        "body": "validation report fail-closed success",
                        "source": "github_repos",
                    }
                ]
            },
            judge_result={"dimension_scores": {"validation_release": 10}},
            tried_queries=set(),
            available_providers=["github_code", "github_issues"],
            plan_count=2,
            max_queries=3,
        )
        anchored = plans[0]["queries"][0]
        self.assertIn("great-expectations/great_expectations", anchored["text"])
        self.assertEqual(anchored["platforms"][0]["repo"], "great-expectations/great_expectations")
        self.assertEqual(
            plans[0]["program_overrides"]["provider_mix"],
            ["github_code", "github_issues"],
        )

    def test_heuristic_searcher_rotates_into_topic_frontier(self):
        goal_case = {
            "dimensions": [{"id": "validation_release", "keywords": ["fail-closed", "validation report"]}],
            "dimension_queries": {"validation_release": ["query a1"]},
            "seed_queries": [],
            "topic_frontier": [
                {
                    "id": "trajectory_subsets",
                    "queries": [
                        {"text": "success failure trajectory pairing", "platforms": [{"name": "huggingface_datasets"}]}
                    ],
                }
            ],
        }
        searcher = HeuristicGoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 82},
            judge_result={"missing_dimensions": ["validation_release"], "dimension_scores": {"validation_release": 14}},
            tried_queries={"query a1::[]"},
            available_providers=["huggingface_datasets"],
            round_history=[],
            plan_count=3,
            max_queries=2,
        )
        labels = [plan["label"] for plan in plans]
        self.assertIn("frontier-trajectory_subsets", labels)
        frontier_plan = next(plan for plan in plans if plan["label"] == "frontier-trajectory_subsets")
        self.assertEqual(frontier_plan["program_overrides"]["topic_frontier"][0]["id"], "trajectory_subsets")
        self.assertGreaterEqual(frontier_plan["program_overrides"]["explore_budget"], 0.7)
        self.assertEqual(frontier_plan["program_overrides"]["provider_mix"], ["huggingface_datasets"])

    def test_goal_director_synthesizes_templates_from_rubric_when_dimension_queries_missing(self):
        goal_case = {
            "seed_queries": ["self improving search loop"],
            "mutation_terms": ["accept reject", "benchmark"],
            "rubric": [
                {"id": "independent_judge", "weight": 20, "keywords": ["judge", "evaluator", "eval"]},
            ],
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 0},
            judge_result={"missing_dimensions": ["independent_judge"], "dimension_scores": {}},
            tried_queries=set(),
            available_providers=["github_repos"],
            plan_count=1,
            max_queries=2,
        )
        self.assertGreaterEqual(len(plans), 1)
        self.assertIn("judge", plans[0]["queries"][0]["text"])

    def test_editor_uses_mutation_terms_as_refinement_fallback(self):
        goal_case = {
            "seed_queries": ["goal loop"],
            "mutation_terms": ["accept reject"],
            "dimension_queries": {},
        }
        editor = HeuristicGoalSearcher(goal_case)
        next_queries = editor.next_queries(
            bundle_state={"accepted_findings": [{"title": "goal loop", "url": "u", "source": "github_repos"}]},
            judge_result={"missing_dimensions": [], "dimension_scores": {}},
            tried_queries=set(),
            max_queries=2,
        )
        self.assertTrue(any("accept reject" in query["text"] for query in next_queries))


if __name__ == "__main__":
    unittest.main()
