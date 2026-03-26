import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_editor import GoalSearcher, HeuristicGoalSearcher, _dimension_family_variants, _normalize_query_spec
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
        self.assertIn("search_backends", plans[0]["program_overrides"])

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
        anchored_plan = next(plan for plan in plans if "anchored" in plan["label"])
        anchored = anchored_plan["queries"][0]
        self.assertIn("great-expectations/great_expectations", anchored["text"])
        self.assertEqual(anchored["platforms"][0]["repo"], "great-expectations/great_expectations")
        self.assertEqual(
            set(anchored_plan["program_overrides"]["provider_mix"]),
            {"github_code", "github_issues"},
        )
        self.assertTrue(anchored_plan["program_overrides"]["acquisition_policy"]["acquire_pages"])
        self.assertIn("code", anchored_plan["program_overrides"]["evidence_policy"]["preferred_content_types"])

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
        self.assertFalse(frontier_plan["program_overrides"]["acquisition_policy"]["acquire_pages"])

    def test_heuristic_searcher_normalizes_string_topic_frontier_entries(self):
        goal_case = {
            "dimensions": [{"id": "validation_release", "keywords": ["fail-closed", "validation report"]}],
            "dimension_queries": {"validation_release": ["query a1"]},
            "seed_queries": [],
            "topic_frontier": ["trajectory_subsets"],
        }
        searcher = HeuristicGoalSearcher(goal_case)
        self.assertEqual(searcher.topic_frontier[0]["id"], "trajectory_subsets")
        self.assertEqual(searcher.topic_frontier[0]["queries"], [])

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

    def test_goal_director_can_emit_context_followup_queries(self):
        goal_case = {
            "seed_queries": [],
            "providers": ["searxng", "ddgs", "github_code"],
            "context_notes": "validation should run after extraction, base release must be fail-closed, success failure trajectory pairing matters.",
            "dimensions": [
                {
                    "id": "validation_release",
                    "weight": 20,
                    "keywords": ["validation report", "fail-closed", "release gate"],
                }
            ],
            "dimension_queries": {
                "validation_release": []
            },
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 0},
            judge_result={"missing_dimensions": ["validation_release"], "dimension_scores": {"validation_release": 5}},
            tried_queries=set(),
            available_providers=["searxng", "ddgs", "github_code"],
            plan_count=3,
            max_queries=3,
        )
        self.assertTrue(any("context-followup" in plan["label"] for plan in plans))
        context_plan = next(plan for plan in plans if "context-followup" in plan["label"])
        self.assertEqual(context_plan["role"], "graph_followup")
        self.assertEqual(context_plan["branch_priority"], 5)
        self.assertTrue(all("validation should run after extraction" not in query["text"] for query in context_plan["queries"]))
        self.assertTrue(any("implementation" in query["text"] for query in context_plan["queries"]))

    def test_goal_director_emits_specialized_validation_release_queries(self):
        goal_case = {
            "seed_queries": [],
            "providers": ["searxng", "ddgs", "github_code", "github_issues", "github_repos"],
            "context_notes": "base release must be fail-closed and publish must stop on validation failure.",
            "dimensions": [
                {
                    "id": "validation_release",
                    "weight": 20,
                    "keywords": ["validation report", "fail-closed", "release gate"],
                }
            ],
            "dimension_queries": {"validation_release": []},
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 0},
            judge_result={"missing_dimensions": ["validation_release"], "dimension_scores": {"validation_release": 0}},
            tried_queries=set(),
            available_providers=["searxng", "ddgs", "github_code", "github_issues", "github_repos"],
            plan_count=3,
            max_queries=3,
        )
        labels = [plan["label"] for plan in plans]
        self.assertIn("dimension_repair-specialized-repair", labels)
        specialized = next(plan for plan in plans if str(plan["label"]).endswith("specialized-repair"))
        texts = [query["text"] for query in specialized["queries"]]
        self.assertTrue(any("post-run validation report" in text or "fail-closed release gate" in text for text in texts))
        self.assertTrue(specialized["program_overrides"]["evidence_policy"]["prefer_acquired_text"])
        self.assertIn("searxng", specialized["program_overrides"]["provider_mix"])
        self.assertIn("ddgs", specialized["program_overrides"]["provider_mix"])
        self.assertIn("github_issues", specialized["program_overrides"]["provider_mix"])

    def test_missing_dimension_heuristic_plan_is_not_crowded_out_by_frontier(self):
        goal_case = {
            "dimensions": [{"id": "validation_release", "keywords": ["validation report", "release gate"]}],
            "seed_queries": [],
            "dimension_queries": {"validation_release": ["validation release query"]},
            "topic_frontier": [
                {"id": "frontier-a", "queries": [{"text": "frontier a", "platforms": []}]},
                {"id": "frontier-b", "queries": [{"text": "frontier b", "platforms": []}]},
            ],
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 80},
            judge_result={"missing_dimensions": ["validation_release"], "dimension_scores": {"validation_release": 0}},
            tried_queries={"validation release query::[]"},
            available_providers=["searxng"],
            plan_count=2,
            max_queries=1,
        )
        labels = [plan["label"] for plan in plans]
        self.assertIn("dimension_repair-specialized-repair", labels)

    def test_goal_director_synthesized_rubric_queries_can_add_structured_platforms(self):
        goal_case = {
            "seed_queries": ["provider doctor cli auth config runtime skip implementation"],
            "mutation_terms": ["health check", "preflight"],
            "providers": ["github_code", "github_issues", "github_repos"],
            "rubric": [
                {"id": "runtime_skip", "weight": 20, "keywords": ["skip", "runtime", "preflight", "before", "unavailable"]},
            ],
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 0},
            judge_result={"missing_dimensions": ["runtime_skip"], "dimension_scores": {}},
            tried_queries=set(),
            available_providers=["github_code", "github_issues", "github_repos"],
            plan_count=1,
            max_queries=2,
        )
        platforms = plans[0]["queries"][0]["platforms"]
        self.assertTrue(platforms)
        self.assertIn("github_code", [platform["name"] for platform in platforms])
        self.assertIn("github_issues", [platform["name"] for platform in platforms])

    def test_provider_mix_keeps_defaults_when_plan_has_unscoped_and_structured_queries(self):
        goal_case = {
            "seed_queries": ["provider doctor cli auth config runtime skip implementation"],
            "mutation_terms": ["health check", "preflight"],
            "providers": ["exa", "tavily", "github_code", "github_issues", "github_repos"],
            "rubric": [
                {"id": "availability", "weight": 20, "keywords": ["available", "availability", "health", "doctor", "status"]},
                {"id": "auth_and_config", "weight": 20, "keywords": ["auth", "authenticated", "login", "config", "configured"]},
            ],
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 0},
            judge_result={"missing_dimensions": ["availability", "auth_and_config"], "dimension_scores": {}},
            tried_queries=set(),
            available_providers=["exa", "tavily", "github_code", "github_issues", "github_repos"],
            plan_count=1,
            max_queries=2,
        )
        provider_mix = plans[0]["program_overrides"]["provider_mix"]
        self.assertIn("exa", provider_mix)
        self.assertIn("tavily", provider_mix)
        self.assertIn("github_issues", provider_mix)
        self.assertIn("search_backends", plans[0]["program_overrides"])
        self.assertIn("population_policy", plans[0]["program_overrides"])

    def test_repair_focus_dimensions_prioritizes_stagnant_dimension(self):
        goal_case = {
            "seed_queries": ["provider doctor"],
            "providers": ["github_repos", "github_issues"],
            "dimension_queries": {
                "runtime_skip": ["runtime skip query"],
                "implementation_signal": ["implementation query"],
            },
            "rubric": [
                {"id": "runtime_skip", "weight": 20, "keywords": ["skip", "runtime"]},
                {"id": "implementation_signal", "weight": 20, "keywords": ["cli", "implementation"]},
            ],
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 80},
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {"runtime_skip": 10, "implementation_signal": 10},
            },
            tried_queries=set(),
            available_providers=["github_repos", "github_issues"],
            active_program={
                "plateau_state": {"dimension_stagnation": {"runtime_skip": 4, "implementation_signal": 1}},
                "query_templates": {
                    "runtime_skip": ["runtime skip query"],
                    "implementation_signal": ["implementation query"],
                },
            },
            plan_count=1,
            max_queries=1,
        )
        self.assertEqual(plans[0]["queries"][0]["text"], "runtime skip query")

    def test_repair_focus_ignores_closed_stagnant_dimensions(self):
        goal_case = {
            "seed_queries": [],
            "providers": ["github_code", "github_issues", "github_repos", "huggingface_datasets"],
            "dimensions": [
                {"id": "validation_release", "weight": 20, "keywords": ["validation report", "release gate", "fail-closed"]},
                {"id": "dedupe_quality", "weight": 20, "keywords": ["semantic deduplication", "near duplicate", "fake gold"]},
            ],
            "dimension_queries": {
                "validation_release": ["post-run validation report"],
                "dedupe_quality": ["semantic deduplication and fake-Gold detection for near-duplicate code pairs"],
            },
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 85},
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {
                    "validation_release": 20,
                    "dedupe_quality": 10,
                },
            },
            tried_queries=set(),
            available_providers=["github_code", "github_issues", "github_repos", "huggingface_datasets"],
            active_program={
                "current_role": "dimension_repair",
                "plateau_state": {"dimension_stagnation": {"validation_release": 5, "dedupe_quality": 1}},
                "query_templates": {
                    "validation_release": ["post-run validation report"],
                    "dedupe_quality": ["semantic deduplication and fake-Gold detection for near-duplicate code pairs"],
                },
            },
            plan_count=2,
            max_queries=2,
        )
        specialized = next(plan for plan in plans if str(plan["label"]).endswith("specialized-repair"))
        specialized_text = " ".join(query["text"] for query in specialized["queries"]).lower()
        self.assertIn("semantic deduplication", specialized_text)
        self.assertNotIn("validation report", specialized_text)

    def test_pair_extract_repair_queries_stay_on_public_pair_vocabulary(self):
        goal_case = {
            "seed_queries": [],
            "providers": ["searxng", "ddgs", "github_code", "github_issues", "github_repos", "huggingface_datasets"],
            "context_notes": "Success and failure trajectory pairing should stay on the same benchmark instance and compare resolved versus unresolved runs.",
            "dimensions": [
                {
                    "id": "pair_extract",
                    "weight": 20,
                    "keywords": ["SWE-bench", "trajectory", "resolved", "unresolved", "success failure", "instance matching"],
                }
            ],
            "dimension_queries": {"pair_extract": []},
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 65},
            judge_result={"missing_dimensions": [], "dimension_scores": {"pair_extract": 5}},
            tried_queries=set(),
            available_providers=["searxng", "ddgs", "github_code", "github_issues", "github_repos", "huggingface_datasets"],
            active_program={"mode": "balanced", "current_role": "dimension_repair"},
            plan_count=3,
            max_queries=3,
        )
        labels = [plan["label"] for plan in plans]
        self.assertIn("dimension_repair-specialized-repair", labels)
        self.assertIn("dimension_repair-context-followup", labels)
        specialized = next(plan for plan in plans if str(plan["label"]).endswith("specialized-repair"))
        context = next(plan for plan in plans if plan["label"] == "dimension_repair-context-followup")
        specialized_text = " ".join(query["text"] for query in specialized["queries"]).lower()
        context_text = " ".join(query["text"] for query in context["queries"]).lower()
        required_terms = {"trajectory", "resolved", "unresolved", "same", "success", "failure"}
        self.assertTrue(any(term in specialized_text for term in required_terms))
        self.assertTrue(any(term in context_text for term in required_terms))
        self.assertNotIn("validation release", specialized_text)
        self.assertNotIn("data validation", context_text)

    def test_dedupe_quality_specialized_repair_uses_dedupe_templates_not_pair_context(self):
        goal_case = {
            "seed_queries": [],
            "providers": ["searxng", "ddgs", "github_code", "github_issues", "github_repos", "huggingface_datasets"],
            "context_notes": (
                "Extraction should preserve raw information first, validation should run after extraction, "
                "success/failure trajectory pairing matters for SWE-bench-style data, base release must be fail-closed, "
                "and semantic dedup plus fake-Gold checks are required."
            ),
            "dimensions": [
                {"id": "pair_extract", "weight": 20, "keywords": ["SWE-bench", "trajectory", "resolved", "unresolved"]},
                {"id": "validation_release", "weight": 20, "keywords": ["validation report", "release gate", "fail-closed"]},
                {
                    "id": "dedupe_quality",
                    "weight": 20,
                    "keywords": [
                        "semantic deduplication",
                        "semantic hashing",
                        "semhash",
                        "near duplicate",
                        "fake gold",
                        "dedup",
                    ],
                },
            ],
            "dimension_queries": {
                "dedupe_quality": [
                    {
                        "text": "semantic deduplication and fake-Gold detection for near-duplicate code pairs",
                        "platforms": [
                            {"name": "github_repos", "query": "semhash", "limit": 5},
                            {"name": "github_issues", "query": "dedup", "limit": 5},
                            {"name": "huggingface_datasets", "query": "semantic dedup", "limit": 5},
                        ],
                    },
                    {
                        "text": "near duplicate detection and identical pair filtering",
                        "platforms": [
                            {"name": "github_code", "query": "\"near duplicate\" dedup", "limit": 5},
                        ],
                    },
                ],
            },
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 73},
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {
                    "pair_extract": 20,
                    "validation_release": 20,
                    "dedupe_quality": 10,
                },
            },
            tried_queries=set(),
            available_providers=["searxng", "ddgs", "github_code", "github_issues", "github_repos", "huggingface_datasets"],
            active_program={"mode": "deep", "current_role": "dimension_repair"},
            plan_count=4,
            max_queries=4,
        )
        specialized = next(plan for plan in plans if str(plan["label"]).endswith("specialized-repair"))
        specialized_text = " ".join(query["text"] for query in specialized["queries"]).lower()
        self.assertIn("semantic deduplication", specialized_text)
        self.assertTrue(any(token in specialized_text for token in ["semhash", "near duplicate", "fake-gold", "dedup"]))
        self.assertNotIn("same benchmark instance", specialized_text)
        self.assertNotIn("validation release", specialized_text)

    def test_dedupe_quality_evidence_strengthening_stays_on_public_dedupe_language(self):
        goal_case = {
            "seed_queries": [],
            "providers": ["searxng", "ddgs", "github_code", "github_issues", "github_repos", "huggingface_datasets"],
            "context_notes": (
                "Need pair extract with same benchmark instance success and failure trajectories; "
                "validation release gates matter; dedupe quality depends on semantic deduplication, "
                "near duplicate filtering, and fake-Gold checks."
            ),
            "dimensions": [
                {"id": "pair_extract", "weight": 20, "keywords": ["same benchmark instance", "successful and failed runs"]},
                {"id": "validation_release", "weight": 20, "keywords": ["validation report", "release gate"]},
                {"id": "dedupe_quality", "weight": 20, "keywords": ["semantic deduplication", "near duplicate filtering", "fake-Gold"]},
            ],
            "dimension_queries": {
                "dedupe_quality": [
                    {"text": "semantic deduplication and fake-Gold detection for near-duplicate code pairs"},
                    {"text": "near duplicate detection and identical pair filtering"},
                ],
            },
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 73},
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {
                    "pair_extract": 20,
                    "validation_release": 20,
                    "dedupe_quality": 10,
                },
            },
            tried_queries=set(),
            available_providers=["searxng", "ddgs", "github_code", "github_issues", "github_repos", "huggingface_datasets"],
            active_program={"mode": "deep", "current_role": "dimension_repair"},
            plan_count=4,
            max_queries=4,
        )
        strengthening = next(plan for plan in plans if plan["label"] == "evidence_strengthening-primary")
        context = next(plan for plan in plans if plan["label"] == "evidence_strengthening-context-followup")
        strengthening_text = " ".join(query["text"] for query in strengthening["queries"]).lower()
        context_text = " ".join(query["text"] for query in context["queries"]).lower()
        self.assertTrue(any(token in strengthening_text for token in ["semantic deduplication", "near duplicate", "fake-gold", "dedup"]))
        self.assertTrue(any(token in context_text for token in ["semantic deduplication", "near duplicate", "fake-gold", "dedup"]))
        self.assertNotIn("same benchmark instance", strengthening_text)
        self.assertNotIn("successful failed runs", context_text)
        self.assertNotIn("resolved unresolved subset", context_text)

    def test_active_program_filters_misaligned_historical_dedupe_queries(self):
        goal_case = {
            "seed_queries": [],
            "providers": ["searxng", "ddgs", "github_code", "github_issues", "github_repos", "huggingface_datasets"],
            "context_notes": (
                "Need pair extract with same benchmark instance success and failure trajectories; "
                "validation release gates matter; dedupe quality depends on semantic deduplication, "
                "near duplicate filtering, and fake-Gold checks."
            ),
            "dimensions": [
                {"id": "extraction_completeness", "weight": 20, "keywords": ["direct extraction", "raw rows"]},
                {"id": "pair_extract", "weight": 20, "keywords": ["same benchmark instance", "successful and failed runs"]},
                {"id": "validation_release", "weight": 20, "keywords": ["validation report", "release gate"]},
                {"id": "dedupe_quality", "weight": 20, "keywords": ["semantic deduplication", "near duplicate filtering", "fake-Gold"]},
            ],
            "dimension_queries": {
                "dedupe_quality": [
                    {"text": "semantic deduplication and fake-Gold detection for near-duplicate code pairs"},
                    {"text": "near duplicate detection and identical pair filtering"},
                ],
            },
        }
        polluted = "validation release same benchmark instance successful and failed runs"
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [], "score": 85},
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {
                    "extraction_completeness": 15,
                    "pair_extract": 20,
                    "validation_release": 20,
                    "dedupe_quality": 10,
                },
            },
            tried_queries=set(),
            available_providers=["searxng", "ddgs", "github_code", "github_issues", "github_repos", "huggingface_datasets"],
            active_program={
                "mode": "deep",
                "current_role": "dimension_repair",
                "query_templates": {
                    "dedupe_quality": [polluted],
                },
                "dimension_strategies": {
                    "dedupe_quality": {
                        "queries": [polluted],
                        "preferred_providers": ["github_code", "github_issues"],
                    }
                },
            },
            plan_count=4,
            max_queries=4,
        )
        specialized = next(plan for plan in plans if str(plan["label"]).endswith("specialized-repair"))
        primary = next(plan for plan in plans if plan["label"] == "evidence_strengthening-primary")
        specialized_text = " ".join(query["text"] for query in specialized["queries"]).lower()
        primary_text = " ".join(query["text"] for query in primary["queries"]).lower()
        self.assertIn("semantic deduplication", specialized_text)
        self.assertNotIn("validation release", specialized_text)
        self.assertNotIn("same benchmark instance", specialized_text)
        self.assertNotIn("validation release", primary_text)
        self.assertNotIn("same benchmark instance", primary_text)

    def test_context_notes_do_not_change_dimension_family(self):
        goal_case = {
            "seed_queries": [],
            "context_notes": (
                "Extraction should preserve raw information first, validation should run after extraction, "
                "success/failure trajectory pairing matters for SWE-bench-style data, base release must be fail-closed, "
                "and semantic dedup plus fake-Gold checks are required."
            ),
            "dimensions": [
                {"id": "extraction_completeness", "weight": 20, "keywords": ["direct conversion", "before after", "original code", "revised code"]},
                {"id": "validation_release", "weight": 20, "keywords": ["validation report", "release gate", "fail-closed", "data contract"]},
                {"id": "pair_extract", "weight": 20, "keywords": ["same benchmark instance", "trajectory", "resolved", "unresolved"]},
                {"id": "dedupe_quality", "weight": 20, "keywords": ["semantic deduplication", "near duplicate", "fake gold"]},
            ],
        }
        validation_variants = " ".join(_dimension_family_variants(goal_case, "validation_release", limit=8)).lower()
        extraction_variants = " ".join(_dimension_family_variants(goal_case, "extraction_completeness", limit=8)).lower()
        self.assertIn("post-run validation report", validation_variants)
        self.assertNotIn("same benchmark instance", validation_variants)
        self.assertNotIn("resolved unresolved subset", validation_variants)
        self.assertNotIn("validation report", extraction_variants)
        self.assertNotIn("release gate", extraction_variants)

    def test_deep_mode_promotes_evidence_strengthening_after_failed_repairs(self):
        goal_case = {
            "seed_queries": [],
            "providers": ["searxng", "ddgs", "github_code", "github_issues", "github_repos"],
            "dimensions": [
                {"id": "validation_release", "weight": 20, "keywords": ["validation report", "release gate"]},
                {"id": "pair_extract", "weight": 20, "keywords": ["pair extract", "paired extraction"]},
            ],
            "dimension_queries": {"validation_release": [], "pair_extract": []},
        }
        searcher = GoalSearcher(goal_case)
        plans = searcher.candidate_plans(
            bundle_state={"accepted_findings": [{"title": "existing evidence", "url": "u", "source": "github_code"}], "score": 48},
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {"validation_release": 8, "pair_extract": 14},
            },
            tried_queries=set(),
            available_providers=["searxng", "ddgs", "github_code", "github_issues", "github_repos"],
            active_program={"mode": "deep"},
            round_history=[
                {"round_role": "dimension_repair", "accepted": False, "queries": [{"text": "repair 1"}]},
                {"round_role": "dimension_repair", "accepted": False, "queries": [{"text": "repair 2"}]},
            ],
            plan_count=3,
            max_queries=3,
        )
        strengthening = next(plan for plan in plans if plan["label"] == "evidence_strengthening-primary")
        self.assertEqual(strengthening["role"], "evidence_strengthening")
        self.assertIn("searxng", strengthening["program_overrides"]["provider_mix"])
        self.assertIn("ddgs", strengthening["program_overrides"]["provider_mix"])
        self.assertIn("github_code", strengthening["program_overrides"]["provider_mix"])
        self.assertIn("github_issues", strengthening["program_overrides"]["provider_mix"])
        self.assertTrue(strengthening["program_overrides"]["evidence_policy"]["cross_verification"])

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
