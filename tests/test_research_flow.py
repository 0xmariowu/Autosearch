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
    def candidate_plans(self, **kwargs):
        return [
            {
                "label": "repair",
                "queries": [{"text": "eval harness regression gate", "platforms": []}],
                "program_overrides": {"provider_mix": ["searxng"]},
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
                {"label": "repair", "intents": [{"text": "eval harness", "platforms": []}]},
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
        self.assertEqual(len(result["query_runs"]), 1)
        self.assertEqual(result["findings"][0]["record_type"], "evidence")
        self.assertEqual(result["query_runs"][0]["local_evidence_count"], 1)
        self.assertIn("graph_node", result)
        self.assertEqual(result["local_evidence_hits"], 1)

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


if __name__ == "__main__":
    unittest.main()
