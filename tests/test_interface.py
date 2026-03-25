import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import interface as api


class InterfaceTests(unittest.TestCase):
    def test_resolve_goal_case_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            goal_root = Path(tmp)
            (goal_root / "case-a.json").write_text(
                '{"id":"goal-a","project":"demo","problem":"p"}',
                encoding="utf-8",
            )
            client = api.AutoSearchInterface(goal_root.parent)
            client.goal_cases_root = goal_root
            payload = client.resolve_goal_case("goal-a")
            self.assertEqual(payload["id"], "goal-a")

    def test_run_goal_case_persists_run_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = api.AutoSearchInterface(tmp)
            client.goal_cases_root = Path(tmp)
            client.goal_runs_root = Path(tmp) / "runs"
            with patch.object(api, "run_goal_bundle_loop", return_value={"goal_id": "demo", "bundle_final": {"score": 82}}):
                result = client.run_goal_case({"id": "demo"}, max_rounds=1, plan_count=1, max_queries=1, persist_run=True)
            self.assertEqual(result["bundle_final"]["score"], 82)
            self.assertIn("run_path", result)
            self.assertTrue(Path(result["run_path"]).exists())

    def test_run_goal_benchmark_returns_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            goal_root = Path(tmp)
            (goal_root / "case-a.json").write_text(
                '{"id":"goal-a","project":"demo","problem":"p"}',
                encoding="utf-8",
            )
            client = api.AutoSearchInterface(goal_root.parent)
            client.goal_cases_root = goal_root
            with patch.object(api, "run_benchmark", return_value={
                "payload": {
                    "generated_at": "now",
                    "max_rounds": 1,
                    "plan_count": 1,
                    "max_queries": 1,
                    "goals": [{"goal_id": "goal-a", "final_score": 80}],
                }
            }):
                payload = client.run_goal_benchmark(["goal-a"], max_rounds=1, plan_count=1, max_queries=1)
            self.assertEqual(payload["goals"][0]["goal_id"], "goal-a")

    def test_build_searcher_judge_session_exposes_both_roles(self):
        goal_case = {
            "id": "goal-a",
            "providers": ["github_repos"],
            "dimensions": [{"id": "pair_extract"}],
            "seed_queries": [{"text": "seed query", "platforms": []}],
            "dimension_queries": {"pair_extract": [{"text": "pair query", "platforms": []}]},
        }
        with patch.object(api, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(api, "available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(api, "search_query", return_value={
                 "query": "pair query",
                 "query_spec": {"text": "pair query", "platforms": []},
                 "baseline_score": 12,
                 "findings": [{"title": "x", "url": "https://x", "source": "github_repos", "query": "pair query"}],
             }), \
             patch.object(api, "evaluate_goal_bundle", return_value={"score": 80, "judge": "heuristic-bundle"}):
            session = api.SearcherJudgeSession(goal_case)
            plans = session.searcher_propose(
                bundle_state={"accepted_findings": [], "score": 0, "dimension_scores": {}, "missing_dimensions": ["pair_extract"]},
                judge_result={"missing_dimensions": ["pair_extract"], "dimension_scores": {}, "matched_dimensions": [], "rationale": ""},
                active_program={"sampling_policy": {"bundle_per_query_cap": 3}},
            )
            result = session.run_searcher_round(
                bundle_state={"accepted_findings": [], "score": 0, "dimension_scores": {}, "missing_dimensions": ["pair_extract"]},
                judge_result={"missing_dimensions": ["pair_extract"], "dimension_scores": {}, "matched_dimensions": [], "rationale": ""},
                active_program={"sampling_policy": {"bundle_per_query_cap": 3}},
            )
        self.assertGreaterEqual(len(plans), 1)
        self.assertEqual(result["plans"][0]["judge_result"]["score"], 80)
        self.assertEqual(result["plans"][0]["query_runs"][0]["query"], "pair query")
        self.assertIn("program_overrides", result["plans"][0])

    def test_searcher_judge_session_falls_back_to_rubric_ids_when_dimensions_missing(self):
        goal_case = {
            "id": "goal-rubric",
            "providers": ["github_repos"],
            "rubric": [{"id": "runtime_skip", "weight": 30, "keywords": ["skip provider"]}],
            "seed_queries": ["provider health check"],
            "dimension_queries": {"runtime_skip": ["provider runtime skip"]},
        }
        with patch.object(api, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(api, "available_platforms", return_value=[{"name": "github_repos", "limit": 5}]):
            session = api.SearcherJudgeSession(goal_case)
            plans = session.searcher_propose()
        self.assertGreaterEqual(len(plans), 1)
        self.assertEqual(plans[0]["queries"][0]["text"], "provider runtime skip")

    def test_searcher_judge_session_can_synthesize_rubric_plan_before_seed_fallback(self):
        goal_case = {
            "id": "goal-seed",
            "providers": ["github_repos"],
            "seed_queries": ["seed query"],
            "dimension_queries": {},
            "rubric": [{"id": "seed", "weight": 20, "keywords": ["seed"]}],
        }
        with patch.object(api, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(api, "available_platforms", return_value=[{"name": "github_repos", "limit": 5}]):
            session = api.SearcherJudgeSession(goal_case)
            plans = session.searcher_propose()
        self.assertEqual(plans[0]["label"], "heuristic-primary")
        self.assertIn("seed", plans[0]["queries"][0]["text"])

    def test_searcher_execute_respects_provider_mix(self):
        goal_case = {
            "id": "goal-mix",
            "providers": ["github_repos", "github_issues"],
            "seed_queries": [],
            "dimension_queries": {},
        }
        with patch.object(api, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(api, "available_platforms", return_value=[
                 {"name": "github_repos", "limit": 5},
                 {"name": "github_issues", "limit": 5},
             ]), \
             patch.object(api, "search_query", return_value={
                 "query": "provider mix query",
                 "query_spec": {"text": "provider mix query", "platforms": [{"name": "github_repos", "limit": 5}]},
                 "baseline_score": 9,
                 "findings": [],
             }) as mocked_search:
            session = api.SearcherJudgeSession(goal_case)
            session.searcher_execute(
                [{"text": "provider mix query", "platforms": [{"name": "github_repos"}, {"name": "github_issues"}]}],
                provider_mix=["github_repos"],
            )
        forwarded_query = mocked_search.call_args.args[0]
        forwarded_platforms = mocked_search.call_args.args[1]
        self.assertEqual([platform["name"] for platform in forwarded_query["platforms"]], ["github_repos"])
        self.assertEqual([platform["name"] for platform in forwarded_platforms], ["github_repos"])


if __name__ == "__main__":
    unittest.main()
