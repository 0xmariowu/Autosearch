import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.executor import execute_research_plan
from research.planner import build_research_plan
from research.synthesizer import synthesize_research_round


class _FakeSearcher:
    goal_case = {
        "dimensions": [
            {"id": "implementation_signal", "keywords": ["runtime skip", "release gate", "validation report"]},
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


class ResearchFlowTests(unittest.TestCase):
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
            judge_result={"missing_dimensions": ["implementation_signal"], "dimension_scores": {"implementation_signal": 5}},
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={"round_roles": ["dimension_repair"]},
            round_history=[{"graph_node": "seed-1"}],
            plan_count=2,
            max_queries=2,
            local_evidence_records=[{
                "record_type": "evidence",
                "title": "Harness implementation patterns",
                "url": "https://example.com",
                "source": "local",
                "query": "harness",
            }],
        )
        self.assertTrue(any(plan["label"] == "graph-followup" for plan in plans))
        self.assertTrue(any(plan["label"] == "graph-decomposition-followup" for plan in plans))
        graph_followup = next(plan for plan in plans if plan["label"] == "graph-followup")
        self.assertTrue(any("runtime skip" in query["text"] or "implementation signal" in query["text"] for query in graph_followup["queries"]))
        self.assertTrue(graph_followup["program_overrides"]["acquisition_policy"]["acquire_pages"])
        self.assertTrue(graph_followup["program_overrides"]["evidence_policy"]["prefer_acquired_text"])
        self.assertTrue(graph_followup["decision"]["cross_verify"])
        self.assertTrue(any(op["op"] == "request_cross_check" for op in graph_followup["planning_ops"]))

    def test_planner_prefers_gap_queue_dimensions_over_missing_dimensions(self):
        plans = build_research_plan(
            searcher=_FakeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={"missing_dimensions": ["implementation_signal"], "dimension_scores": {"implementation_signal": 5}},
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={"round_roles": ["dimension_repair"]},
            round_history=[],
            plan_count=1,
            max_queries=1,
            gap_queue=[{"dimension": "validation_release", "status": "open", "priority": 1}],
        )
        self.assertEqual(plans[0]["branch_targets"], ["validation_release"])

    def test_planner_disables_cross_verification_when_action_policy_blocks_it(self):
        plans = build_research_plan(
            searcher=_FakeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={"missing_dimensions": ["implementation_signal"], "dimension_scores": {"implementation_signal": 5}},
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={"round_roles": ["dimension_repair"]},
            round_history=[{"role": "graph_followup"}],
            plan_count=2,
            max_queries=2,
            local_evidence_records=[{
                "record_type": "evidence",
                "title": "Harness implementation patterns",
                "url": "https://example.com",
                "source": "local",
                "query": "harness",
            }],
            action_policy={"allowed_actions": ["search", "repair"], "disabled_reasons": {"cross_verify": "recent_cross_verification"}},
        )
        self.assertFalse(any(plan["label"] == "graph-followup" for plan in plans))
        self.assertFalse(any(plan["label"] == "graph-decomposition-followup" for plan in plans))

    def test_planner_respects_retired_mutation_kinds_and_budget(self):
        plans = build_research_plan(
            searcher=_FakeSearcher(),
            bundle_state={"accepted_findings": []},
            judge_result={"missing_dimensions": ["implementation_signal"], "dimension_scores": {"implementation_signal": 5}},
            tried_queries=set(),
            available_providers=["searxng"],
            active_program={
                "round_roles": ["dimension_repair", "orthogonal_probe"],
                "population_policy": {
                    "branch_budget_per_round": {"followup": 0, "repair": 1, "probe": 1, "breadth": 1},
                    "recursive_depth_limit": 1,
                },
                "evolution_stats": {"retired_mutation_kinds": ["dimension_repair"]},
            },
            round_history=[{"graph_node": "seed-1", "branch_depth": 1}],
            plan_count=3,
            max_queries=2,
            local_evidence_records=[{
                "record_type": "evidence",
                "title": "Harness implementation patterns",
                "url": "https://example.com",
                "source": "local",
                "query": "harness",
            }],
        )
        self.assertTrue(plans)
        self.assertTrue(all(plan["branch_type"] != "followup" for plan in plans))
        self.assertTrue(all(plan["role"] != "dimension_repair" for plan in plans))

    def test_executor_returns_query_runs_and_findings(self):
        with patch("research.executor.search_query", return_value={
            "query": "eval harness",
            "query_spec": {"text": "eval harness", "platforms": []},
            "baseline_score": 10,
            "findings": [{"record_type": "evidence", "title": "A", "url": "https://example.com", "source": "searxng", "query": "eval harness"}],
        }):
            result = execute_research_plan(
                {
                    "label": "repair",
                    "intents": [{"text": "eval harness", "platforms": []}],
                    "decision": {
                        "provider_mix": ["searxng"],
                        "cross_verify": True,
                        "cross_verification_queries": [{"text": "eval harness comparison", "platforms": []}],
                        "sampling_policy": {},
                        "acquisition_policy": {},
                        "evidence_policy": {},
                    },
                    "planning_ops": [{"op": "request_cross_check", "target": "implementation"}],
                },
                default_platforms=[{"name": "searxng", "limit": 5}],
                provider_mix=["searxng"],
                query_key_fn=lambda q: str(q),
                local_evidence_records=[{
                    "record_type": "evidence",
                    "title": "Local Eval Harness",
                    "url": "https://local.example/harness",
                    "canonical_text": "eval harness planner executor",
                    "source": "local",
                    "query": "eval harness",
                }],
            )
        self.assertEqual(len(result["query_runs"]), 2)
        self.assertEqual(result["findings"][0]["record_type"], "evidence")
        self.assertEqual(result["query_runs"][0]["local_evidence_count"], 1)
        self.assertIn("graph_node", result)
        self.assertEqual(result["local_evidence_hits"], 1)
        self.assertTrue(result["cross_verification"]["enabled"])
        self.assertEqual(result["cross_verification"]["verification_query_count"], 1)
        self.assertEqual(result["planning_ops"][0]["op"], "request_cross_check")

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
                {"label": "repair", "role": "dimension_repair", "intents": [{"text": "repository implementation guide", "platforms": []}]},
                default_platforms=[{"name": "searxng", "limit": 5}, {"name": "github_repos", "limit": 5}],
                provider_mix=["searxng", "github_repos"],
                backend_roles={"breadth": ["searxng"], "repos": ["github_repos"]},
                query_key_fn=lambda q: str(q),
            )
        self.assertEqual(observed["platforms"], ["github_repos"])

    def test_synthesizer_builds_bundle_and_repair_hints(self):
        goal_case = {
            "dimensions": [
                {"id": "implementation", "weight": 20, "keywords": ["implementation", "code"]},
                {"id": "regression", "weight": 20, "keywords": ["regression", "gate"]},
            ]
        }
        result = synthesize_research_round(
            goal_case,
            existing_findings=[],
            round_findings=[{
                "record_type": "evidence",
                "title": "implementation code",
                "url": "https://example.com",
                "body": "implementation detail",
                "source": "searxng",
                "query": "implementation",
            }],
            harness={"bundle_policy": {"per_query_cap": 5, "per_source_cap": 10, "per_domain_cap": 10}},
            graph_plan={
                "graph_node": "repair-d1-n1",
                "graph_edges": [{"from": "seed-1", "to": "repair-d1-n1", "kind": "branch"}],
                "branch_type": "repair",
                "branch_subgoal": "implementation",
                "branch_targets": ["implementation"],
            },
            gap_queue=[{"gap_id": "gap:implementation", "dimension": "implementation", "status": "open", "priority": 1}],
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
        self.assertIn("gap_queue", result)
        self.assertIn("gap_queue", result["routeable_output"])
        self.assertIn("regression", [item["dimension"] for item in result["gap_queue"]])


if __name__ == "__main__":
    unittest.main()
