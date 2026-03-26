import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import interface as api


class InterfaceTests(unittest.TestCase):
    def test_api_info_exposes_product_metadata(self):
        client = api.AutoSearchInterface(REPO_ROOT)
        payload = client.api_info()
        self.assertEqual(payload["api_name"], "autosearch-public-api")
        self.assertEqual(payload["_api"]["method"], "api_info")
        self.assertTrue(
            any(item["name"] == "run_goal_case" for item in payload["methods"])
        )

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
            with patch.object(
                api,
                "run_goal_bundle_loop",
                return_value={
                    "goal_id": "demo",
                    "bundle_final": {"score": 82},
                    "routeable_output": {"research_packet": {"packet_id": "demo:82:1"}},
                },
            ) as mocked_loop:
                result = client.run_goal_case(
                    {"id": "demo"},
                    mode="deep",
                    max_rounds=1,
                    plan_count=1,
                    max_queries=1,
                    target_score=95,
                    plateau_rounds=2,
                    persist_run=True,
                )
            self.assertEqual(result["bundle_final"]["score"], 82)
            self.assertIn("run_path", result)
            self.assertEqual(result["research_packet"]["packet_id"], "demo:82:1")
            self.assertTrue(Path(result["run_path"]).exists())
            self.assertEqual(result["_api"]["method"], "run_goal_case")
            self.assertEqual(mocked_loop.call_args.kwargs["target_score_override"], 95)
            self.assertEqual(mocked_loop.call_args.kwargs["plateau_rounds_override"], 2)
            self.assertEqual(mocked_loop.call_args.args[0]["mode"], "deep")

    def test_run_goal_benchmark_returns_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            goal_root = Path(tmp)
            (goal_root / "case-a.json").write_text(
                '{"id":"goal-a","project":"demo","problem":"p"}',
                encoding="utf-8",
            )
            client = api.AutoSearchInterface(goal_root.parent)
            client.goal_cases_root = goal_root
            with patch.object(
                api,
                "run_benchmark",
                return_value={
                    "payload": {
                        "generated_at": "now",
                        "max_rounds": 1,
                        "plan_count": 1,
                        "max_queries": 1,
                        "goals": [{"goal_id": "goal-a", "final_score": 80}],
                    }
                },
            ) as mocked_benchmark:
                payload = client.run_goal_benchmark(
                    ["goal-a"],
                    max_rounds=1,
                    plan_count=1,
                    max_queries=1,
                    target_score=100,
                    plateau_rounds=3,
                )
            self.assertEqual(payload["goals"][0]["goal_id"], "goal-a")
            self.assertEqual(payload["_api"]["method"], "run_goal_benchmark")
            self.assertEqual(mocked_benchmark.call_args.kwargs["target_score"], 100)
            self.assertEqual(mocked_benchmark.call_args.kwargs["plateau_rounds"], 3)

    def test_run_goal_benchmark_can_include_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            goal_root = Path(tmp)
            (goal_root / "case-a.json").write_text(
                '{"id":"goal-a","project":"demo","problem":"p"}',
                encoding="utf-8",
            )
            client = api.AutoSearchInterface(goal_root.parent)
            client.goal_cases_root = goal_root
            with patch.object(
                api,
                "run_benchmark",
                return_value={
                    "payload": {"goals": [{"goal_id": "goal-a"}]},
                    "results": [{"goal_id": "goal-a", "rounds": []}],
                },
            ):
                payload = client.run_goal_benchmark(
                    ["goal-a"],
                    include_results=True,
                )
        self.assertIn("payload", payload)
        self.assertIn("results", payload)
        self.assertEqual(payload["_api"]["method"], "run_goal_benchmark")

    def test_optimize_goal_forwards_target_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = api.AutoSearchInterface(tmp)
            client.goal_cases_root = Path(tmp)
            with patch.object(
                api.AutoSearchInterface,
                "run_goal_case",
                return_value={"goal_id": "demo"},
            ) as mocked_run:
                result = client.optimize_goal(
                    {"id": "demo"},
                    mode="deep",
                    target_score=100,
                    max_rounds=6,
                    plateau_rounds=2,
                    plan_count=2,
                    max_queries=3,
                    persist_run=False,
                )
            self.assertEqual(result["goal_id"], "demo")
            self.assertEqual(mocked_run.call_args.args[0]["id"], "demo")
            self.assertEqual(mocked_run.call_args.kwargs["mode"], "deep")
            self.assertEqual(mocked_run.call_args.kwargs["target_score"], 100)
            self.assertEqual(mocked_run.call_args.kwargs["plateau_rounds"], 2)

    def test_optimize_goals_forwards_target_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = api.AutoSearchInterface(tmp)
            with patch.object(
                api.AutoSearchInterface,
                "run_goal_benchmark",
                return_value={"goals": []},
            ) as mocked_run:
                result = client.optimize_goals(
                    ["goal-a", "goal-b"],
                    mode="speed",
                    target_score=95,
                    max_rounds=4,
                    plateau_rounds=2,
                    plan_count=2,
                    max_queries=3,
                )
            self.assertEqual(result["goals"], [])
            self.assertEqual(mocked_run.call_args.args[0], ["goal-a", "goal-b"])
            self.assertEqual(mocked_run.call_args.kwargs["mode"], "speed")
            self.assertEqual(mocked_run.call_args.kwargs["target_score"], 95)
            self.assertEqual(mocked_run.call_args.kwargs["plateau_rounds"], 2)

    def test_run_watch_uses_watch_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = api.AutoSearchInterface(tmp)
            with patch.object(
                api, "_run_watch", return_value={"watch_id": "w1"}
            ) as mocked_run:
                result = client.run_watch({"watch_id": "w1", "goal_id": "goal-a"})
        self.assertEqual(result["watch_id"], "w1")
        self.assertEqual(result["_api"]["method"], "run_watch")
        self.assertEqual(
            mocked_run.call_args.kwargs["resolve_goal_case"], client.resolve_goal_case
        )

    def test_build_searcher_judge_session_exposes_both_roles(self):
        goal_case = {
            "id": "goal-a",
            "providers": ["github_repos"],
            "dimensions": [{"id": "pair_extract"}],
            "seed_queries": [{"text": "seed query", "platforms": []}],
            "dimension_queries": {
                "pair_extract": [{"text": "pair query", "platforms": []}]
            },
        }
        with (
            patch.object(
                api, "refresh_source_capability", return_value={"sources": {}}
            ),
            patch.object(
                api,
                "available_platforms",
                return_value=[{"name": "github_repos", "limit": 5}],
            ),
            patch.object(
                api,
                "search_query",
                return_value={
                    "query": "pair query",
                    "query_spec": {"text": "pair query", "platforms": []},
                    "baseline_score": 12,
                    "findings": [
                        {
                            "title": "x",
                            "url": "https://x",
                            "source": "github_repos",
                            "query": "pair query",
                        }
                    ],
                },
            ),
            patch.object(
                api,
                "evaluate_goal_bundle",
                return_value={"score": 80, "judge": "heuristic-bundle"},
            ),
        ):
            session = api.SearcherJudgeSession(goal_case)
            plans = session.searcher_propose(
                bundle_state={
                    "accepted_findings": [],
                    "score": 0,
                    "dimension_scores": {},
                    "missing_dimensions": ["pair_extract"],
                },
                judge_result={
                    "missing_dimensions": ["pair_extract"],
                    "dimension_scores": {},
                    "matched_dimensions": [],
                    "rationale": "",
                },
                active_program={"sampling_policy": {"bundle_per_query_cap": 3}},
            )
            result = session.run_searcher_round(
                bundle_state={
                    "accepted_findings": [],
                    "score": 0,
                    "dimension_scores": {},
                    "missing_dimensions": ["pair_extract"],
                },
                judge_result={
                    "missing_dimensions": ["pair_extract"],
                    "dimension_scores": {},
                    "matched_dimensions": [],
                    "rationale": "",
                },
                active_program={"sampling_policy": {"bundle_per_query_cap": 3}},
            )
        self.assertGreaterEqual(len(plans), 1)
        self.assertEqual(result["plans"][0]["judge_result"]["score"], 80)
        self.assertEqual(result["plans"][0]["query_runs"][0]["query"], "pair query")
        self.assertIn("program_overrides", result["plans"][0])

    def test_searcher_judge_session_falls_back_to_rubric_ids_when_dimensions_missing(
        self,
    ):
        goal_case = {
            "id": "goal-rubric",
            "providers": ["github_repos"],
            "rubric": [
                {"id": "runtime_skip", "weight": 30, "keywords": ["skip provider"]}
            ],
            "seed_queries": ["provider health check"],
            "dimension_queries": {"runtime_skip": ["provider runtime skip"]},
        }
        with (
            patch.object(
                api, "refresh_source_capability", return_value={"sources": {}}
            ),
            patch.object(
                api,
                "available_platforms",
                return_value=[{"name": "github_repos", "limit": 5}],
            ),
        ):
            session = api.SearcherJudgeSession(goal_case)
            plans = session.searcher_propose()
        self.assertGreaterEqual(len(plans), 1)
        self.assertEqual(plans[0]["queries"][0]["text"], "provider runtime skip")

    def test_searcher_judge_session_can_synthesize_rubric_plan_before_seed_fallback(
        self,
    ):
        goal_case = {
            "id": "goal-seed",
            "providers": ["github_repos"],
            "seed_queries": ["seed query"],
            "dimension_queries": {},
            "rubric": [{"id": "seed", "weight": 20, "keywords": ["seed"]}],
        }
        with (
            patch.object(
                api, "refresh_source_capability", return_value={"sources": {}}
            ),
            patch.object(
                api,
                "available_platforms",
                return_value=[{"name": "github_repos", "limit": 5}],
            ),
        ):
            session = api.SearcherJudgeSession(goal_case)
            plans = session.searcher_propose()
        self.assertEqual(plans[0]["label"], "dimension_repair-primary")
        self.assertIn("seed", plans[0]["queries"][0]["text"])

    def test_searcher_execute_respects_provider_mix(self):
        goal_case = {
            "id": "goal-mix",
            "providers": ["github_repos", "github_issues"],
            "seed_queries": [],
            "dimension_queries": {},
        }
        with (
            patch.object(
                api, "refresh_source_capability", return_value={"sources": {}}
            ),
            patch.object(
                api,
                "available_platforms",
                return_value=[
                    {"name": "github_repos", "limit": 5},
                    {"name": "github_issues", "limit": 5},
                ],
            ),
            patch.object(
                api,
                "search_query",
                return_value={
                    "query": "provider mix query",
                    "query_spec": {
                        "text": "provider mix query",
                        "platforms": [{"name": "github_repos", "limit": 5}],
                    },
                    "baseline_score": 9,
                    "findings": [],
                },
            ) as mocked_search,
        ):
            session = api.SearcherJudgeSession(goal_case)
            session.searcher_execute(
                [
                    {
                        "text": "provider mix query",
                        "platforms": [
                            {"name": "github_repos"},
                            {"name": "github_issues"},
                        ],
                    }
                ],
                provider_mix=["github_repos"],
            )
        forwarded_query = mocked_search.call_args.args[0]
        forwarded_platforms = mocked_search.call_args.args[1]
        self.assertEqual(
            [platform["name"] for platform in forwarded_query["platforms"]],
            ["github_repos"],
        )
        self.assertEqual(
            [platform["name"] for platform in forwarded_platforms], ["github_repos"]
        )

    def test_search_goal_query_uses_goal_platforms_and_provider_mix(self):
        goal_case = {
            "id": "goal-mix",
            "providers": ["github_repos", "github_issues"],
        }
        with (
            patch.object(
                api, "refresh_source_capability", return_value={"sources": {}}
            ),
            patch.object(
                api,
                "available_platforms",
                return_value=[
                    {"name": "github_repos", "limit": 5},
                    {"name": "github_issues", "limit": 5},
                ],
            ),
            patch.object(
                api,
                "search_query",
                return_value={
                    "query": "provider mix query",
                    "query_spec": {
                        "text": "provider mix query",
                        "platforms": [{"name": "github_repos", "limit": 5}],
                    },
                    "baseline_score": 9,
                    "findings": [],
                },
            ) as mocked_search,
        ):
            client = api.AutoSearchInterface(REPO_ROOT)
            client.search_goal_query(
                goal_case,
                {
                    "text": "provider mix query",
                    "platforms": [{"name": "github_repos"}, {"name": "github_issues"}],
                },
                provider_mix=["github_repos"],
            )
        forwarded_query = mocked_search.call_args.args[0]
        forwarded_platforms = mocked_search.call_args.args[1]
        self.assertEqual(
            [platform["name"] for platform in forwarded_query["platforms"]],
            ["github_repos"],
        )
        self.assertEqual(
            [platform["name"] for platform in forwarded_platforms], ["github_repos"]
        )

    def test_replay_goal_queries_returns_runs_and_findings(self):
        goal_case = {
            "id": "goal-replay",
            "providers": ["searxng"],
        }
        with (
            patch.object(
                api, "refresh_source_capability", return_value={"sources": {}}
            ),
            patch.object(
                api,
                "available_platforms",
                return_value=[{"name": "searxng", "limit": 5}],
            ),
            patch.object(
                api,
                "replay_queries",
                return_value=(
                    [
                        {
                            "query": "q1",
                            "query_spec": {"text": "q1", "platforms": []},
                            "baseline_score": 3,
                            "finding_count": 1,
                            "sample_findings": [],
                        }
                    ],
                    [
                        {
                            "record_type": "evidence",
                            "title": "A",
                            "url": "https://example.com",
                        }
                    ],
                ),
            ),
        ):
            client = api.AutoSearchInterface(REPO_ROOT)
            result = client.replay_goal_queries(
                goal_case, [{"text": "q1", "platforms": []}]
            )
        self.assertEqual(result["queries"][0]["text"], "q1")
        self.assertEqual(result["query_runs"][0]["query"], "q1")
        self.assertEqual(result["findings"][0]["title"], "A")
        self.assertEqual(result["_api"]["method"], "replay_goal_queries")

    def test_research_phase_wrappers_delegate(self):
        goal_case = {
            "id": "goal-research",
            "providers": ["searxng"],
            "seed_queries": [],
            "dimension_queries": {},
        }
        with (
            patch.object(
                api, "refresh_source_capability", return_value={"sources": {}}
            ),
            patch.object(
                api,
                "available_platforms",
                return_value=[{"name": "searxng", "limit": 5}],
            ),
            patch.object(
                api, "build_research_plan", return_value=[{"label": "repair"}]
            ) as mocked_plan,
            patch.object(
                api,
                "execute_research_plan",
                return_value={"label": "repair", "query_runs": []},
            ) as mocked_execute,
            patch.object(
                api,
                "synthesize_research_round",
                return_value={"bundle": [], "routeable_output": {}},
            ) as mocked_synthesize,
        ):
            client = api.AutoSearchInterface(REPO_ROOT)
            plans = client.build_research_plan(goal_case, plan_count=1, max_queries=1)
            execution = client.execute_research_plan(goal_case, {"label": "repair"})
            synthesized = client.synthesize_research_round(
                goal_case,
                existing_findings=[],
                round_findings=[],
                harness={"bundle_per_query_cap": 1},
                effective_target_score=95,
            )
        self.assertEqual(plans["plans"][0]["label"], "repair")
        self.assertEqual(
            mocked_plan.call_args.kwargs["available_providers"], ["searxng"]
        )
        self.assertEqual(execution["label"], "repair")
        self.assertIs(mocked_execute.call_args.kwargs["query_key_fn"], api.query_key)
        self.assertEqual(synthesized["bundle"], [])
        self.assertEqual(mocked_synthesize.call_args.args[0]["id"], "goal-research")
        self.assertEqual(
            mocked_synthesize.call_args.kwargs["effective_target_score"], 95
        )
        self.assertEqual(plans["_api"]["method"], "build_research_plan")
        self.assertEqual(execution["_api"]["method"], "execute_research_plan")
        self.assertEqual(synthesized["_api"]["method"], "synthesize_research_round")

    def test_acquisition_and_evidence_wrappers_delegate(self):
        with (
            patch.object(
                api,
                "_fetch_document",
                return_value=SimpleNamespace(url="https://example.com"),
            ) as mocked_fetch,
            patch.object(
                api, "_enrich_evidence_record", return_value={"acquired": True}
            ) as mocked_enrich,
            patch.object(
                api, "_build_markdown_views", return_value={"fit_markdown": "x"}
            ) as mocked_markdown,
            patch.object(
                api, "_chunk_document", return_value=[{"text": "x"}]
            ) as mocked_chunk,
            patch.object(
                api,
                "_normalize_result_record",
                return_value={"record_type": "evidence"},
            ) as mocked_normalize_result,
            patch.object(
                api,
                "_normalize_acquired_document",
                return_value={"record_type": "evidence"},
            ) as mocked_normalize_doc,
            patch.object(
                api,
                "_normalize_evidence_record",
                return_value={"record_type": "evidence"},
            ) as mocked_normalize_evidence,
            patch.object(
                api, "_coerce_evidence_record", return_value={"record_type": "evidence"}
            ) as mocked_coerce_one,
            patch.object(
                api,
                "_coerce_evidence_records",
                return_value=[{"record_type": "evidence"}],
            ) as mocked_coerce_many,
        ):
            client = api.AutoSearchInterface(REPO_ROOT)
            fetched = client.fetch_document("https://example.com", query="demo")
            enriched = client.enrich_record(
                {"url": "https://example.com"}, query="demo"
            )
            markdown = client.build_markdown_views("hello world", query="hello")
            chunks = client.chunk_document("hello world", query="hello")
            normalized = client.normalize_result_record(
                SimpleNamespace(title="A"), "demo"
            )
            normalized_doc = client.normalize_acquired_document(
                SimpleNamespace(title="A"), source="web", query="demo"
            )
            normalized_evidence = client.normalize_evidence_record({"title": "A"})
            coerced = client.coerce_evidence_record({"title": "A"})
            coerced_many = client.coerce_evidence_records([{"title": "A"}])
        self.assertEqual(fetched["document"]["url"], "https://example.com")
        self.assertTrue(enriched["acquired"])
        self.assertEqual(markdown["fit_markdown"], "x")
        self.assertEqual(chunks["chunks"][0]["text"], "x")
        self.assertEqual(normalized["record"]["record_type"], "evidence")
        self.assertEqual(normalized_doc["record"]["record_type"], "evidence")
        self.assertEqual(normalized_evidence["record"]["record_type"], "evidence")
        self.assertEqual(coerced["record"]["record_type"], "evidence")
        self.assertEqual(coerced_many["records"][0]["record_type"], "evidence")
        self.assertEqual(mocked_fetch.call_args.kwargs["query"], "demo")
        self.assertEqual(mocked_enrich.call_args.kwargs["query"], "demo")
        self.assertEqual(mocked_markdown.call_args.kwargs["query"], "hello")
        self.assertEqual(mocked_chunk.call_args.kwargs["query"], "hello")
        self.assertEqual(mocked_normalize_result.call_args.args[1], "demo")
        self.assertEqual(mocked_normalize_doc.call_args.kwargs["source"], "web")
        self.assertEqual(mocked_coerce_one.call_args.args[0]["title"], "A")
        self.assertEqual(mocked_coerce_many.call_args.args[0][0]["title"], "A")
        self.assertEqual(fetched["_api"]["method"], "fetch_document")
        self.assertEqual(enriched["_api"]["method"], "enrich_record")
        self.assertEqual(markdown["_api"]["method"], "build_markdown_views")
        self.assertEqual(chunks["_api"]["method"], "chunk_document")

    def test_routeable_builders_delegate(self):
        class _Packet:
            def to_dict(self):
                return {"packet_id": "goal-route:80:1"}

        goal_case = {"id": "goal-route"}
        with (
            patch.object(
                api, "build_routeable_output", return_value={"goal_id": "goal-route"}
            ) as mocked_routeable,
            patch.object(
                api, "build_research_packet", return_value=_Packet()
            ) as mocked_packet,
        ):
            client = api.AutoSearchInterface(REPO_ROOT)
            routeable = client.build_routeable_output(
                goal_case,
                bundle=[{"url": "https://example.com"}],
                judge_result={"score": 80},
                effective_target_score=95,
            )
            packet = client.build_research_packet(
                goal_case,
                bundle=[{"url": "https://example.com"}],
                judge_result={"score": 80},
            )
        self.assertEqual(routeable["goal_id"], "goal-route")
        self.assertEqual(packet["packet_id"], "goal-route:80:1")
        self.assertEqual(mocked_routeable.call_args.args[0]["id"], "goal-route")
        self.assertEqual(
            mocked_routeable.call_args.kwargs["effective_target_score"], 95
        )
        self.assertEqual(
            mocked_packet.call_args.kwargs["goal_case"]["id"], "goal-route"
        )
        self.assertEqual(routeable["_api"]["method"], "build_routeable_output")
        self.assertEqual(packet["_api"]["method"], "build_research_packet")


if __name__ == "__main__":
    unittest.main()
