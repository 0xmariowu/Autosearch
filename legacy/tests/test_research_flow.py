import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_editor import GoalSearcher
from research.executor import execute_research_plan
from research.planner import (
    _augment_queries,
    _decomposition_followups,
    _follow_up_queries,
    _missed_keyword_phrases,
    _repair_terms,
    build_research_plan,
)
from research.synthesizer import synthesize_research_round


def _load_atoms_goal_case() -> dict:
    return json.loads(
        (REPO_ROOT / "goal_cases" / "atoms-auto-mining-perfect.json").read_text(
            encoding="utf-8"
        )
    )


class _FakeSearcher:
    goal_case = {
        "dimensions": [
            {
                "id": "implementation_signal",
                "keywords": ["runtime skip", "release gate", "validation report"],
            },
        ]
    }

    def candidate_plans(self, **kwargs):
        return [
            {
                "label": "repair",
                "queries": [{"text": "eval harness regression gate", "platforms": []}],
                "program_overrides": {"provider_mix": ["searxng"]},
                "branch_priority": 4,
            }
        ]


class _PairSearcher:
    goal_case = {
        "dimensions": [
            {
                "id": "pair_extract",
                "weight": 20,
                "keywords": [
                    "SWE-bench",
                    "trajectory",
                    "resolved",
                    "unresolved",
                    "success failure",
                    "instance matching",
                ],
                "aliases": [
                    "same benchmark instance",
                    "successful and failed runs",
                    "verified trajectories",
                ],
            },
        ]
    }

    def candidate_plans(self, **kwargs):
        return [
            {
                "label": "repair",
                "queries": [
                    {
                        "text": "same benchmark instance successful and failed runs",
                        "platforms": [],
                    }
                ],
                "program_overrides": {"provider_mix": ["searxng"]},
                "branch_priority": 4,
            }
        ]


class _DedupeSearcher:
    goal_case = {
        "dimensions": [
            {
                "id": "dedupe_quality",
                "weight": 20,
                "keywords": [
                    "semantic deduplication",
                    "semantic hashing",
                    "semhash",
                    "near duplicate",
                    "dedup",
                ],
            },
        ]
    }

    def candidate_plans(self, **kwargs):
        return [
            {
                "label": "repair",
                "queries": [
                    {
                        "text": "semantic deduplication and fake-Gold detection",
                        "platforms": [],
                    }
                ],
                "program_overrides": {"provider_mix": ["searxng"]},
                "branch_priority": 4,
            }
        ]


class ResearchFlowTests(unittest.TestCase):
    def test_missed_keyword_phrases_returns_weakest_dimension_misses(self):
        phrases = _missed_keyword_phrases(
            {
                "dimension_scores": {
                    "dedupe_quality": 5,
                    "validation_release": 12,
                },
                "dimension_keyword_misses": {
                    "validation_release": ["release gate", "validation report"],
                    "dedupe_quality": [
                        "near duplicate detection",
                        "duplicate detection",
                        "near duplicate detection",
                    ],
                },
            }
        )

        self.assertEqual(
            phrases,
            [
                "near duplicate detection",
                "duplicate detection",
                "release gate",
                "validation report",
            ],
        )

    def test_repair_terms_uses_dimension_keywords(self):
        repairs = _repair_terms(
            {
                "missing_dimensions": [],
                "dimension_scores": {
                    "dedupe_quality": 10,
                    "validation_release": 20,
                },
            },
            _DedupeSearcher.goal_case,
        )
        self.assertEqual(repairs[0], "semantic deduplication")
        self.assertNotIn("dedupe quality", repairs)

    def test_follow_up_queries_dedupe_uses_dedupe_templates(self):
        queries = _follow_up_queries(
            goal_case=_DedupeSearcher.goal_case,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "semhash implementation notes",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "dedupe",
                }
            ],
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {"dedupe_quality": 10},
            },
            max_queries=6,
            tried_queries=set(),
        )
        texts = [query["text"].lower() for query in queries]
        self.assertTrue(
            any(
                "dedup" in text or "duplicate" in text or "semhash" in text
                for text in texts
            )
        )
        self.assertFalse(
            any(
                "repository" in text
                or "release issue" in text
                or "source proof" in text
                for text in texts
            )
        )

    def test_follow_up_queries_prioritizes_missed_keywords(self):
        queries = _follow_up_queries(
            goal_case=_DedupeSearcher.goal_case,
            local_evidence_records=[],
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {"dedupe_quality": 15},
                "dimension_keyword_misses": {
                    "dedupe_quality": [
                        "near duplicate detection",
                        "duplicate detection",
                        "fake gold",
                    ]
                },
            },
            max_queries=4,
            tried_queries=set(),
        )

        self.assertEqual(queries[0]["text"], "near duplicate detection implementation")
        self.assertEqual(
            queries[1]["text"], "near duplicate detection algorithm comparison"
        )
        self.assertTrue(
            any(query["text"].startswith("duplicate detection") for query in queries)
        )

    def test_decomposition_followups_dedupe_uses_dedupe_templates(self):
        queries = _decomposition_followups(
            goal_case=_DedupeSearcher.goal_case,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "semhash implementation notes",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "dedupe",
                }
            ],
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {"dedupe_quality": 10},
            },
            max_queries=6,
            tried_queries=set(),
        )
        texts = [query["text"].lower() for query in queries]
        self.assertTrue(
            any(
                "dedup" in text or "duplicate" in text or "semhash" in text
                for text in texts
            )
        )
        self.assertFalse(
            any(
                "repository source" in text
                or "release blocker" in text
                or "issue discussion" in text
                for text in texts
            )
        )

    def test_decomposition_followups_with_real_atoms_goal_case_do_not_use_bare_dedupe_quality(
        self,
    ):
        queries = _decomposition_followups(
            goal_case=_load_atoms_goal_case(),
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "semhash implementation notes",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "dedupe",
                }
            ],
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {
                    "dedupe_quality": 10,
                    "extraction_completeness": 20,
                    "label_separation": 20,
                    "pair_extract": 20,
                    "validation_release": 20,
                },
            },
            max_queries=6,
            tried_queries=set(),
        )
        texts = [query["text"].lower() for query in queries]
        self.assertTrue(any("semantic deduplication" in text for text in texts))
        self.assertFalse(any("dedupe quality" in text for text in texts))

    def test_follow_up_queries_pair_still_uses_pair_templates(self):
        queries = _follow_up_queries(
            goal_case=_PairSearcher.goal_case,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "same benchmark instance successful and failed runs",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "pair",
                }
            ],
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {"pair_extract": 5},
            },
            max_queries=6,
            tried_queries=set(),
        )
        texts = [query["text"].lower() for query in queries]
        self.assertTrue(
            any(
                "trajectory" in text or "resolved" in text or "same task" in text
                for text in texts
            )
        )
        self.assertFalse(any("repository implementation" in text for text in texts))

    def test_augment_queries_uses_keywords_not_bare_ids(self):
        queries = _augment_queries(
            [],
            goal_case=_DedupeSearcher.goal_case,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "semhash implementation notes",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "dedupe",
                }
            ],
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {"dedupe_quality": 10},
            },
            tried_queries=set(),
            max_queries=3,
        )
        texts = [query["text"].lower() for query in queries]
        self.assertTrue(
            any("semantic deduplication" in text or "semhash" in text for text in texts)
        )
        self.assertFalse(any("dedupe quality" in text for text in texts))

    def test_planner_returns_intents(self):
        plans = build_research_plan(
            searcher=_FakeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={"missing_dimensions": ["implementation"]},
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={},
            round_history=[],
            plan_count=1,
            max_queries=1,
        )
        self.assertEqual(plans[0]["label"], "repair")
        self.assertEqual(plans[0]["intents"][0]["text"], "eval harness regression gate")
        self.assertEqual(plans[0]["stage"], "breadth")
        self.assertEqual(plans[0]["branch_type"], "breadth")
        self.assertTrue(plans[0]["graph_node"].startswith("breadth-d1-"))
        self.assertEqual(plans[0]["branch_subgoal"], "implementation")
        self.assertEqual(plans[0]["graph_edges"], [])
        self.assertEqual(plans[0]["branch_priority"], 4)
        self.assertIn("decision", plans[0])
        self.assertIn("planning_ops", plans[0])

    def test_planner_adds_follow_up_branch_from_local_evidence(self):
        plans = build_research_plan(
            searcher=_FakeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={
                "missing_dimensions": ["implementation_signal"],
                "dimension_scores": {"implementation_signal": 5},
            },
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={"round_roles": ["dimension_repair"]},
            round_history=[{"graph_node": "seed-1"}],
            plan_count=2,
            max_queries=2,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "Harness implementation patterns",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "harness",
                }
            ],
        )
        self.assertTrue(any(plan["label"] == "graph-followup" for plan in plans))
        self.assertTrue(
            any(plan["label"] == "graph-decomposition-followup" for plan in plans)
        )
        graph_followup = next(
            plan for plan in plans if plan["label"] == "graph-followup"
        )
        self.assertTrue(
            any(
                "runtime skip" in query["text"]
                or "implementation signal" in query["text"]
                for query in graph_followup["queries"]
            )
        )
        self.assertTrue(
            graph_followup["program_overrides"]["acquisition_policy"]["acquire_pages"]
        )
        self.assertTrue(
            graph_followup["program_overrides"]["evidence_policy"][
                "prefer_acquired_text"
            ]
        )
        self.assertIn(
            "code",
            graph_followup["program_overrides"]["evidence_policy"][
                "preferred_content_types"
            ],
        )
        self.assertTrue(
            any(
                marker in query["text"]
                for query in graph_followup["queries"]
                for marker in ("repository", "issue", "release", "source")
            )
        )
        self.assertTrue(graph_followup["decision"]["cross_verify"])
        self.assertTrue(
            any(
                op["op"] == "request_cross_check"
                for op in graph_followup["planning_ops"]
            )
        )

    def test_planner_makes_repair_branch_evidence_first(self):
        plans = build_research_plan(
            searcher=_FakeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={
                "missing_dimensions": ["implementation_signal"],
                "dimension_scores": {"implementation_signal": 5},
            },
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={"round_roles": ["dimension_repair"], "mode": "balanced"},
            round_history=[],
            plan_count=1,
            max_queries=1,
        )
        repair = plans[0]
        self.assertEqual(repair["branch_type"], "repair")
        self.assertTrue(repair["decision"]["acquisition_policy"]["acquire_pages"])
        self.assertTrue(repair["decision"]["evidence_policy"]["prefer_acquired_text"])
        self.assertIn(
            "code", repair["decision"]["evidence_policy"]["preferred_content_types"]
        )
        self.assertIn(
            "repository",
            repair["decision"]["evidence_policy"]["preferred_content_types"],
        )

    def test_planner_pair_extract_followups_use_public_trajectory_language(self):
        plans = build_research_plan(
            searcher=_PairSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {"pair_extract": 5},
            },
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={"round_roles": ["dimension_repair"]},
            round_history=[{"graph_node": "seed-1"}],
            plan_count=2,
            max_queries=2,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "same benchmark instance successful and failed runs",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "pair extract",
                }
            ],
        )
        graph_followup = next(
            plan for plan in plans if plan["label"] == "graph-followup"
        )
        graph_decomposition = next(
            plan for plan in plans if plan["label"] == "graph-decomposition-followup"
        )
        followup_text = " ".join(
            query["text"] for query in graph_followup["queries"]
        ).lower()
        decomposition_text = " ".join(
            query["text"] for query in graph_decomposition["queries"]
        ).lower()
        required_terms = {
            "trajectory",
            "resolved",
            "unresolved",
            "same",
            "success",
            "failure",
        }
        self.assertTrue(any(term in followup_text for term in required_terms))
        self.assertTrue(any(term in decomposition_text for term in required_terms))
        self.assertNotIn("pair extract repository source", decomposition_text)

    def test_planner_dedupe_followups_use_public_dedupe_language(self):
        plans = build_research_plan(
            searcher=_DedupeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={
                "missing_dimensions": [],
                "dimension_scores": {"dedupe_quality": 10},
            },
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={"round_roles": ["dimension_repair"]},
            round_history=[{"graph_node": "seed-1"}],
            plan_count=2,
            max_queries=2,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "semantic deduplication and fake-Gold detection",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "dedupe",
                }
            ],
        )
        graph_followup = next(
            plan for plan in plans if plan["label"] == "graph-followup"
        )
        graph_decomposition = next(
            plan for plan in plans if plan["label"] == "graph-decomposition-followup"
        )
        followup_text = " ".join(
            query["text"] for query in graph_followup["queries"]
        ).lower()
        decomposition_text = " ".join(
            query["text"] for query in graph_decomposition["queries"]
        ).lower()
        self.assertTrue(
            any(
                term in followup_text
                for term in ["semantic deduplication", "dedup", "duplicate", "semhash"]
            )
        )
        self.assertTrue(
            any(
                term in decomposition_text
                for term in ["semantic deduplication", "dedup", "duplicate", "semhash"]
            )
        )
        self.assertNotIn("dedupe quality repository source", decomposition_text)

    def test_build_research_plan_with_real_goal_searcher_keeps_dedupe_queries_on_repair_and_followup(
        self,
    ):
        goal_case = _load_atoms_goal_case()
        searcher = GoalSearcher(goal_case)
        judge_result = {
            "score": 85,
            "missing_dimensions": [],
            "matched_dimensions": [
                "extraction_completeness",
                "label_separation",
                "pair_extract",
                "validation_release",
            ],
            "dimension_scores": {
                "extraction_completeness": 15,
                "label_separation": 20,
                "pair_extract": 20,
                "validation_release": 20,
                "dedupe_quality": 10,
            },
        }

        plans = build_research_plan(
            searcher=searcher,
            bundle_state={
                "accepted_findings": [],
                "accepted_queries": [],
                "score": 85,
                "dimension_scores": dict(judge_result["dimension_scores"]),
                "missing_dimensions": [],
                "matched_dimensions": list(judge_result["matched_dimensions"]),
            },
            judge_result=judge_result,
            tried_queries=set(),
            available_providers=[
                "searxng",
                "github_repos",
                "github_issues",
                "github_code",
                "huggingface_datasets",
            ],
            active_program={
                "mode": "deep",
                "round_roles": ["dimension_repair"],
                "current_role": "dimension_repair",
                "repair_policy": {"target_weak_dimensions": 1},
                "population_policy": {
                    "branch_budget_per_round": {
                        "breadth": 1,
                        "repair": 2,
                        "followup": 2,
                        "probe": 1,
                        "research": 1,
                    },
                    "recursive_depth_limit": 4,
                },
            },
            round_history=[{"graph_node": "seed-1"}],
            plan_count=4,
            max_queries=4,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "semantic deduplication and fake-Gold detection for near-duplicate code pairs",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "semantic deduplication",
                }
            ],
        )

        repair_followups = [
            plan for plan in plans if plan["branch_type"] in {"repair", "followup"}
        ]
        self.assertTrue(repair_followups)
        for plan in repair_followups:
            text = " ".join(query["text"] for query in plan["queries"]).lower()
            self.assertTrue(
                any(
                    term in text
                    for term in ("dedup", "duplicate", "semhash", "semantic")
                ),
                plan,
            )

    def test_planner_prefers_gap_queue_dimensions_over_missing_dimensions(self):
        plans = build_research_plan(
            searcher=_FakeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={
                "missing_dimensions": ["implementation_signal"],
                "dimension_scores": {"implementation_signal": 5},
            },
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={"round_roles": ["dimension_repair"]},
            round_history=[],
            plan_count=1,
            max_queries=1,
            gap_queue=[
                {"dimension": "validation_release", "status": "open", "priority": 1}
            ],
        )
        self.assertEqual(plans[0]["branch_targets"], ["validation_release"])

    def test_planner_disables_cross_verification_when_action_policy_blocks_it(self):
        plans = build_research_plan(
            searcher=_FakeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={
                "missing_dimensions": ["implementation_signal"],
                "dimension_scores": {"implementation_signal": 5},
            },
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={"round_roles": ["dimension_repair"]},
            round_history=[{"role": "graph_followup"}],
            plan_count=2,
            max_queries=2,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "Harness implementation patterns",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "harness",
                }
            ],
            action_policy={
                "allowed_actions": ["search", "repair"],
                "disabled_reasons": {"cross_verify": "recent_cross_verification"},
            },
        )
        self.assertFalse(any(plan["label"] == "graph-followup" for plan in plans))
        self.assertFalse(
            any(plan["label"] == "graph-decomposition-followup" for plan in plans)
        )

    def test_planner_respects_retired_mutation_kinds_and_budget(self):
        plans = build_research_plan(
            searcher=_FakeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={
                "missing_dimensions": ["implementation_signal"],
                "dimension_scores": {"implementation_signal": 5},
            },
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={
                "round_roles": ["dimension_repair", "orthogonal_probe"],
                "population_policy": {
                    "branch_budget_per_round": {
                        "followup": 0,
                        "repair": 1,
                        "probe": 1,
                        "breadth": 1,
                    },
                    "recursive_depth_limit": 1,
                },
                "evolution_stats": {"retired_mutation_kinds": ["dimension_repair"]},
            },
            round_history=[{"graph_node": "seed-1", "branch_depth": 1}],
            plan_count=3,
            max_queries=2,
            local_evidence_records=[
                {
                    "record_type": "evidence",
                    "title": "Harness implementation patterns",
                    "url": "https://example.com",
                    "source": "local",
                    "query": "harness",
                }
            ],
        )
        self.assertTrue(plans)
        self.assertTrue(all(plan["branch_type"] != "followup" for plan in plans))
        self.assertTrue(all(plan["role"] != "dimension_repair" for plan in plans))

    def test_executor_returns_query_runs_and_findings(self):
        with patch(
            "research.executor.search_query",
            return_value={
                "query": "eval harness",
                "query_spec": {"text": "eval harness", "platforms": []},
                "baseline_score": 10,
                "findings": [
                    {
                        "record_type": "evidence",
                        "title": "A",
                        "url": "https://example.com",
                        "source": "searxng",
                        "query": "eval harness",
                    }
                ],
            },
        ):
            result = execute_research_plan(
                {
                    "label": "repair",
                    "intents": [{"text": "eval harness", "platforms": []}],
                    "decision": {
                        "provider_mix": ["searxng"],
                        "cross_verify": True,
                        "cross_verification_queries": [
                            {"text": "eval harness comparison", "platforms": []}
                        ],
                        "sampling_policy": {},
                        "acquisition_policy": {},
                        "evidence_policy": {},
                    },
                    "planning_ops": [
                        {"op": "request_cross_check", "target": "implementation"}
                    ],
                },
                default_platforms=[{"name": "searxng", "limit": 5}],
                provider_mix=["searxng"],
                query_key_fn=lambda q: str(q),
                local_evidence_records=[
                    {
                        "record_type": "evidence",
                        "title": "Local Eval Harness",
                        "url": "https://local.example/harness",
                        "canonical_text": "eval harness planner executor",
                        "source": "local",
                        "query": "eval harness",
                    }
                ],
            )
        self.assertEqual(len(result["query_runs"]), 2)
        self.assertEqual(result["findings"][0]["record_type"], "evidence")
        self.assertEqual(result["query_runs"][0]["local_evidence_count"], 1)
        self.assertIn("graph_node", result)
        self.assertEqual(result["local_evidence_hits"], 1)
        self.assertTrue(result["cross_verification"]["enabled"])
        self.assertEqual(result["cross_verification"]["verification_query_count"], 1)
        self.assertEqual(result["planning_ops"][0]["op"], "request_cross_check")
        self.assertEqual(result["deep_steps"][0]["kind"], "search")
        self.assertEqual(result["deep_steps"][1]["kind"], "read")

    def test_executor_deep_mode_generates_reason_step_and_followup(self):
        calls = {"count": 0}

        def _fake_search(query, platforms, sampling_policy=None):
            calls["count"] += 1
            return {
                "query": query["text"],
                "query_spec": query,
                "baseline_score": 10,
                "findings": [
                    {
                        "record_type": "evidence",
                        "title": "Release gate validator implementation",
                        "url": f"https://example.com/{calls['count']}",
                        "source": "searxng",
                        "query": query["text"],
                        "extract": "validation contract release blocker implementation details",
                    }
                ],
            }

        with patch("research.executor.search_query", side_effect=_fake_search):
            result = execute_research_plan(
                {
                    "label": "repair",
                    "intents": [{"text": "validation release gate", "platforms": []}],
                    "decision": {
                        "mode": "deep",
                        "provider_mix": ["searxng"],
                        "sampling_policy": {},
                        "acquisition_policy": {"acquire_pages": True},
                        "evidence_policy": {"prefer_acquired_text": True},
                    },
                },
                default_platforms=[{"name": "searxng", "limit": 5}],
                provider_mix=["searxng"],
                query_key_fn=lambda q: str(q),
            )
        self.assertGreaterEqual(calls["count"], 2)
        self.assertTrue(any(step["kind"] == "reason" for step in result["deep_steps"]))

    def test_executor_uses_backend_roles_to_narrow_platforms(self):
        observed = {}

        def _fake_search(query, platforms, sampling_policy=None):
            observed["platforms"] = [platform["name"] for platform in platforms]
            return {
                "query": query["text"],
                "query_spec": query,
                "baseline_score": 5,
                "findings": [],
            }

        with patch("research.executor.search_query", side_effect=_fake_search):
            execute_research_plan(
                {
                    "label": "repair",
                    "role": "dimension_repair",
                    "intents": [
                        {"text": "repository implementation guide", "platforms": []}
                    ],
                },
                default_platforms=[
                    {"name": "searxng", "limit": 5},
                    {"name": "github_repos", "limit": 5},
                ],
                provider_mix=["searxng", "github_repos"],
                backend_roles={"breadth": ["searxng"], "repos": ["github_repos"]},
                query_key_fn=lambda q: str(q),
            )
        self.assertEqual(observed["platforms"], ["github_repos"])

    def test_executor_preserves_explicit_structured_platforms_over_classification(self):
        observed = {}

        def _fake_search(query, platforms, sampling_policy=None):
            observed["platforms"] = [platform["name"] for platform in platforms]
            observed["query"] = query
            return {
                "query": query["text"],
                "query_spec": query,
                "baseline_score": 5,
                "findings": [],
            }

        with patch("research.executor.search_query", side_effect=_fake_search):
            execute_research_plan(
                {
                    "label": "repair",
                    "role": "dimension_repair",
                    "intents": [
                        {
                            "text": "validation release fail-closed release gate",
                            "platforms": [
                                {
                                    "name": "github_code",
                                    "query": '"fail-closed release gate"',
                                    "limit": 5,
                                },
                                {
                                    "name": "github_issues",
                                    "query": "fail-closed release gate",
                                    "limit": 5,
                                },
                                {
                                    "name": "github_repos",
                                    "query": "fail-closed release gate",
                                    "limit": 5,
                                },
                            ],
                        }
                    ],
                },
                default_platforms=[
                    {"name": "searxng", "limit": 5},
                    {"name": "ddgs", "limit": 5},
                    {"name": "github_code", "limit": 5},
                    {"name": "github_issues", "limit": 5},
                    {"name": "github_repos", "limit": 5},
                ],
                provider_mix=[
                    "searxng",
                    "ddgs",
                    "github_code",
                    "github_issues",
                    "github_repos",
                ],
                backend_roles={"breadth": ["searxng", "ddgs"]},
                query_key_fn=lambda q: str(q),
            )
        self.assertEqual(
            observed["platforms"], ["github_code", "github_issues", "github_repos"]
        )
        self.assertEqual(
            [platform["name"] for platform in observed["query"]["platforms"]],
            ["github_code", "github_issues", "github_repos"],
        )

    def test_executor_treats_unscoped_query_with_new_provider_mix_as_new_attempt(self):
        observed = {"count": 0}

        def _fake_search(query, platforms, sampling_policy=None):
            observed["count"] += 1
            return {
                "query": query["text"],
                "query_spec": query,
                "baseline_score": 5,
                "findings": [],
            }

        with patch("research.executor.search_query", side_effect=_fake_search):
            execute_research_plan(
                {
                    "label": "repair",
                    "role": "dimension_repair",
                    "intents": [
                        {"text": "validation report implementation", "platforms": []}
                    ],
                },
                default_platforms=[
                    {"name": "searxng", "limit": 5},
                    {"name": "ddgs", "limit": 5},
                ],
                provider_mix=["searxng", "ddgs"],
                query_key_fn=lambda q: f"{q['text']}::{q.get('platforms', [])!r}",
                tried_queries={
                    "validation report implementation::[]::providers=['github_code']"
                },
            )
        self.assertEqual(observed["count"], 1)

    def test_synthesizer_builds_bundle_and_repair_hints(self):
        goal_case = {
            "dimensions": [
                {
                    "id": "implementation",
                    "weight": 20,
                    "keywords": ["implementation", "code"],
                },
                {"id": "regression", "weight": 20, "keywords": ["regression", "gate"]},
            ]
        }
        result = synthesize_research_round(
            goal_case,
            existing_findings=[],
            round_findings=[
                {
                    "record_type": "evidence",
                    "title": "implementation code",
                    "url": "https://example.com",
                    "body": "implementation detail",
                    "source": "searxng",
                    "query": "implementation",
                }
            ],
            harness={
                "bundle_policy": {
                    "per_query_cap": 5,
                    "per_source_cap": 10,
                    "per_domain_cap": 10,
                }
            },
            graph_plan={
                "graph_node": "repair-d1-n1",
                "graph_edges": [
                    {"from": "seed-1", "to": "repair-d1-n1", "kind": "branch"}
                ],
                "branch_type": "repair",
                "branch_subgoal": "implementation",
                "branch_targets": ["implementation"],
            },
            gap_queue=[
                {
                    "gap_id": "gap:implementation",
                    "dimension": "implementation",
                    "status": "open",
                    "priority": 1,
                }
            ],
        )
        self.assertIn("bundle", result)
        self.assertIn("judge_result", result)
        self.assertIn("research_bundle", result)
        self.assertEqual(result["research_bundle"]["goal_id"], "goal")
        self.assertIn("weakest_dimension", result["repair_hints"])
        self.assertIn("routes", result["routeable_output"])
        self.assertIn("score_gap", result["routeable_output"])
        self.assertIn("next_actions", result["routeable_output"])
        self.assertIn("handoff_packets", result["routeable_output"])
        self.assertIn("search_graph", result)
        self.assertIn("scheduler", result["search_graph"])
        self.assertIn("graph_handoff", result["routeable_output"])
        self.assertIn("next_branch_mode", result["routeable_output"]["graph_handoff"])
        self.assertIn("cross_verification", result["search_graph"])
        self.assertIn("cross_verification", result["routeable_output"])
        self.assertIn("research_packet", result["routeable_output"])
        self.assertIn("deep_loop", result["search_graph"])
        self.assertEqual(
            result["search_graph"]["deep_loop"]["steps"][0]["kind"], "search"
        )
        self.assertIn("gap_queue", result)
        self.assertIn("gap_queue", result["routeable_output"])
        self.assertIn("regression", [item["dimension"] for item in result["gap_queue"]])
        self.assertIn("planning_ops_summary", result["routeable_output"])

    def test_synthesizer_uses_effective_target_score_for_routeable_output(self):
        goal_case = {
            "target_score": 100,
            "dimensions": [
                {
                    "id": "implementation",
                    "weight": 20,
                    "keywords": ["implementation", "code"],
                },
            ],
        }
        result = synthesize_research_round(
            goal_case,
            existing_findings=[],
            round_findings=[
                {
                    "record_type": "evidence",
                    "title": "implementation code",
                    "url": "https://example.com",
                    "body": "implementation detail",
                    "source": "searxng",
                    "query": "implementation",
                }
            ],
            harness={
                "bundle_policy": {
                    "per_query_cap": 5,
                    "per_source_cap": 10,
                    "per_domain_cap": 10,
                }
            },
            effective_target_score=95,
        )
        self.assertEqual(result["routeable_output"]["score_gap"], 75)

    def test_synthesizer_keeps_low_score_pair_extract_open_in_gap_queue(self):
        goal_case = {
            "dimensions": [
                {
                    "id": "pair_extract",
                    "weight": 20,
                    "keywords": [
                        "SWE-bench",
                        "trajectory",
                        "SWE-agent",
                        "SWE-Gym",
                        "resolved",
                        "unresolved",
                        "success failure",
                        "instance matching",
                    ],
                },
                {
                    "id": "validation_release",
                    "weight": 20,
                    "keywords": ["validation report", "release gate"],
                },
            ]
        }
        result = synthesize_research_round(
            goal_case,
            existing_findings=[],
            round_findings=[
                {
                    "record_type": "evidence",
                    "title": "SWE-bench Lite dataset summary",
                    "url": "https://example.com",
                    "body": "Benchmark overview page.",
                    "source": "web",
                    "query": "swe-bench benchmark summary",
                }
            ],
            harness={
                "bundle_policy": {
                    "per_query_cap": 5,
                    "per_source_cap": 10,
                    "per_domain_cap": 10,
                }
            },
            gap_queue=[
                {
                    "gap_id": "gap:pair_extract",
                    "dimension": "pair_extract",
                    "status": "open",
                    "priority": 1,
                },
                {
                    "gap_id": "gap:validation_release",
                    "dimension": "validation_release",
                    "status": "open",
                    "priority": 2,
                },
            ],
        )
        statuses = {item["dimension"]: item["status"] for item in result["gap_queue"]}
        self.assertEqual(statuses["pair_extract"], "open")

    def test_synthesizer_reports_contradictions_and_consensus(self):
        goal_case = {
            "dimensions": [
                {
                    "id": "implementation",
                    "weight": 20,
                    "keywords": ["implementation", "verified"],
                },
            ]
        }
        result = synthesize_research_round(
            goal_case,
            existing_findings=[],
            round_findings=[
                {
                    "record_type": "evidence",
                    "title": "Implementation works in production",
                    "url": "https://a.example.com",
                    "body": "verified stable success",
                    "source": "searxng",
                    "query": "implementation verified",
                },
                {
                    "record_type": "evidence",
                    "title": "Implementation has regression issue",
                    "url": "https://b.example.com",
                    "body": "failing bug limitation",
                    "source": "ddgs",
                    "query": "implementation verified",
                },
            ],
            harness={
                "bundle_policy": {
                    "per_query_cap": 5,
                    "per_source_cap": 10,
                    "per_domain_cap": 10,
                }
            },
            graph_plan={
                "decision": {"cross_verify": True},
                "cross_verification": {"verification_query_count": 2},
                "query_runs": [
                    {"query": "implementation verified"},
                    {"query": "implementation criticism"},
                ],
            },
        )
        verification = result["routeable_output"]["cross_verification"]
        self.assertTrue(verification["contradiction_detected"])
        self.assertEqual(verification["consensus_strength"], "contested")
        self.assertEqual(verification["stance_counts"]["positive"], 1)
        self.assertEqual(verification["stance_counts"]["negative"], 1)
        self.assertTrue(verification["contradiction_pairs"])
        self.assertTrue(verification["claim_alignment"])
        self.assertTrue(verification["contradiction_clusters"])
        self.assertIn("searxng", verification["source_dispute_map"])
        self.assertIn("ddgs", verification["source_dispute_map"])
        self.assertTrue(verification["source_dispute_map"]["searxng"]["claims"])

    def test_synthesizer_avoids_self_collision_contradiction_pairs(self):
        goal_case = {
            "dimensions": [
                {
                    "id": "implementation",
                    "weight": 20,
                    "keywords": ["implementation", "verified"],
                },
            ]
        }
        result = synthesize_research_round(
            goal_case,
            existing_findings=[],
            round_findings=[
                {
                    "record_type": "evidence",
                    "title": "Implementation works well in production. Implementation has a regression issue.",
                    "url": "https://same.example.com/item",
                    "body": "This stable implementation succeeds in production. This release has a bug limitation.",
                    "source": "searxng",
                    "query": "implementation verified",
                },
            ],
            harness={
                "bundle_policy": {
                    "per_query_cap": 5,
                    "per_source_cap": 10,
                    "per_domain_cap": 10,
                }
            },
            graph_plan={
                "decision": {"cross_verify": True},
                "cross_verification": {"verification_query_count": 2},
                "query_runs": [{"query": "implementation verified"}],
            },
        )
        verification = result["routeable_output"]["cross_verification"]
        self.assertFalse(
            any(
                pair["left_url"] == pair["right_url"]
                and pair["left_source"] == pair["right_source"]
                for pair in verification["contradiction_pairs"]
            ),
        )


if __name__ == "__main__":
    unittest.main()
