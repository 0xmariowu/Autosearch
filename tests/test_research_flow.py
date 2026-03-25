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
            )
        self.assertEqual(len(result["query_runs"]), 1)
        self.assertEqual(result["findings"][0]["record_type"], "evidence")

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
        self.assertIn("weakest_dimension", result["repair_hints"])


if __name__ == "__main__":
    unittest.main()
