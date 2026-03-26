import json
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
from goal_editor import GoalSearcher as RealGoalSearcher


def _load_atoms_goal_case() -> dict:
    return json.loads((REPO_ROOT / "goal_cases" / "atoms-auto-mining-perfect.json").read_text(encoding="utf-8"))


class GoalBundleLoopTests(unittest.TestCase):
    def test_run_goal_bundle_loop_keeps_dedupe_vocabulary_when_dedupe_is_only_open_dimension(self):
        goal_case = _load_atoms_goal_case()
        real_searcher = RealGoalSearcher(goal_case)
        searcher = SimpleNamespace(
            initial_queries=lambda: [],
            candidate_plans=real_searcher.candidate_plans,
        )
        warm_judge = {
            "score": 85,
            "dimension_scores": {
                "extraction_completeness": 15,
                "label_separation": 20,
                "pair_extract": 20,
                "validation_release": 20,
                "dedupe_quality": 10,
            },
            "missing_dimensions": [],
            "matched_dimensions": [
                "extraction_completeness",
                "label_separation",
                "pair_extract",
                "validation_release",
            ],
            "rationale": "dedupe is the only weak dimension",
            "judge": "heuristic-bundle",
        }
        accepted_program = {
            "program_id": "seed-program",
            "queries": [{"text": "semantic deduplication baseline", "platforms": []}],
            "sampling_policy": {},
            "stop_rules": {},
            "plateau_state": {},
            "mode": "deep",
            "mode_policy_overrides": {},
            "round_roles": ["dimension_repair"],
            "current_role": "dimension_repair",
            "provider_mix": ["searxng", "github_repos", "github_issues", "github_code", "huggingface_datasets"],
            "search_backends": ["searxng", "github_repos", "github_issues", "github_code", "huggingface_datasets"],
            "backend_roles": {},
            "topic_frontier": [],
            "query_templates": {},
            "dimension_strategies": {},
            "acquisition_policy": {},
            "evidence_policy": {},
            "repair_policy": {"target_weak_dimensions": 1},
            "population_policy": {
                "plan_count": 4,
                "max_queries": 4,
                "recursive_depth_limit": 4,
                "branch_budget_per_round": {"breadth": 1, "repair": 2, "followup": 2, "probe": 1, "research": 1},
            },
            "explore_budget": 0.2,
            "exploit_budget": 0.8,
        }

        class _FakeIndex:
            def __init__(self, path):
                self.records = []

            def load_all(self):
                return list(self.records)

            def add(self, records):
                self.records.extend(list(records or []))

        def fake_execute(plan, **kwargs):
            queries = list(plan.get("intents") or [])
            query_runs = [
                {
                    "query": query["text"],
                    "query_spec": query,
                    "baseline_score": 10,
                    "finding_count": 1,
                    "sample_findings": [],
                }
                for query in queries
            ]
            findings = [
                {
                    "title": query["text"],
                    "url": f"https://example.com/{index}",
                    "source": "github_repos",
                    "query": query["text"],
                }
                for index, query in enumerate(queries, start=1)
            ]
            return {
                "label": plan.get("label", ""),
                "queries": queries,
                "role": plan.get("role", ""),
                "branch_type": plan.get("branch_type", ""),
                "branch_subgoal": plan.get("branch_subgoal", ""),
                "stage": plan.get("stage", ""),
                "graph_node": plan.get("graph_node", ""),
                "graph_edges": list(plan.get("graph_edges") or []),
                "branch_targets": list(plan.get("branch_targets") or []),
                "branch_depth": int(plan.get("branch_depth", 0) or 0),
                "decision": {"cross_verify": False},
                "planning_ops": [],
                "cross_verification": {"enabled": False, "verification_query_count": 0},
                "deep_steps": [{"kind": "search", "summary": plan.get("label", ""), "metadata": {"round": 1}}],
                "local_evidence_hits": len(plan.get("local_evidence_records") or []),
                "query_keys": [f"{query['text']}::{query.get('platforms', [])!r}" for query in queries],
                "query_runs": query_runs,
                "findings": findings,
            }

        def fake_synthesize(goal_case, existing_findings, round_findings, harness, graph_plan, gap_queue, planning_ops):
            return {
                "bundle": list(round_findings),
                "research_bundle": {"bundle_id": "bundle-dedupe"},
                "judge_result": dict(warm_judge),
                "harness_metrics": {
                    "total_findings": len(round_findings),
                    "new_unique_urls": max(len(round_findings), 1),
                    "novelty_ratio": 1.0,
                    "source_diversity": 1.0,
                    "source_concentration": 1.0,
                    "query_concentration": 1.0,
                },
                "search_graph": {"deep_loop": {"steps": [{"kind": "search", "summary": graph_plan.get("label", "")}]}},
                "repair_hints": {},
                "gap_queue": [],
                "routeable_output": {
                    "goal_id": goal_case["id"],
                    "research_packet": {"packet_id": "packet-dedupe"},
                    "score_gap": 15,
                },
            }

        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[
                 {"name": "searxng", "limit": 5},
                 {"name": "github_repos", "limit": 5},
                 {"name": "github_issues", "limit": 5},
                 {"name": "github_code", "limit": 5},
                 {"name": "huggingface_datasets", "limit": 5},
             ]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": goal_case["id"], "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher", return_value=searcher), \
             patch.object(gbl, "load_accepted_program", return_value=accepted_program), \
             patch.object(gbl, "LocalEvidenceIndex", _FakeIndex), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(gbl, "_replay_queries", return_value=(
                 [{"query_spec": {"text": "semantic deduplication baseline", "platforms": []}, "baseline_score": 10}],
                 [{"title": "semantic deduplication baseline", "url": "https://example.com/warm", "source": "github_repos", "query": "semantic deduplication baseline"}],
             )), \
             patch.object(gbl, "build_bundle", side_effect=lambda existing, findings, harness: list(findings)), \
             patch.object(gbl, "evaluate_goal_bundle", return_value=warm_judge), \
             patch.object(gbl, "execute_research_plan", side_effect=fake_execute), \
             patch.object(gbl, "synthesize_research_round", side_effect=fake_synthesize), \
             patch.object(gbl, "archive_candidate_program", return_value=Path("/tmp/archive.json")), \
             patch.object(gbl, "save_population_snapshot", return_value={
                 "latest": Path("/tmp/latest.json"),
                 "history": Path("/tmp/history.json"),
                 "latest_lineage": Path("/tmp/latest-lineage.json"),
                 "lineage_history": Path("/tmp/lineage-history.json"),
             }), \
             patch.object(gbl, "candidate_rank", side_effect=lambda item: int(item.get("score") or item["result"]["score"])), \
             patch.object(gbl, "evaluate_acceptance", return_value={"accepted": True, "candidate_score": 85, "anti_cheat_failures": [], "anti_cheat_warnings": []}), \
             patch.object(gbl, "save_accepted_program"):
            result = gbl.run_goal_bundle_loop(goal_case, max_rounds=1, plan_count_override=4, max_queries_override=4)

        repair_followups = [
            plan
            for plan in result["rounds"][0]["editor_plans"]
            if plan["branch_type"] in {"repair", "followup"}
        ]
        self.assertTrue(repair_followups)
        for plan in repair_followups:
            text = " ".join(query["text"] for query in plan["queries"]).lower()
            self.assertTrue(any(term in text for term in ("dedup", "duplicate", "semhash", "semantic")), plan)

    def test_update_gap_queue_keeps_low_score_pair_extract_open(self):
        goal_case = {
            "dimensions": [
                {"id": "pair_extract", "weight": 20, "keywords": ["SWE-bench", "trajectory"]},
                {"id": "validation_release", "weight": 20, "keywords": ["validation report", "release gate"]},
            ]
        }
        queue = gbl.update_gap_queue(
            goal_case=goal_case,
            previous_queue=[],
            judge_result={
                "missing_dimensions": [],
                "matched_dimensions": ["pair_extract", "validation_release"],
                "dimension_scores": {"pair_extract": 5, "validation_release": 20},
            },
            round_index=1,
        )
        pair_gap = next(item for item in queue if item["dimension"] == "pair_extract")
        validation_gap = next(item for item in queue if item["dimension"] == "validation_release")
        self.assertEqual(pair_gap["status"], "open")
        self.assertEqual(validation_gap["status"], "satisfied")

    def test_sample_findings_prioritizes_structurally_strong_pair_evidence(self):
        findings = [
            {
                "title": "Weak SWE-Bench trajectory mention",
                "body": "SWE-agent replay for a SWE-Bench trajectory issue.",
                "url": "https://example.com/weak",
                "source": "github_issues",
                "query": "pair",
            },
            {
                "title": "Verified trajectories include successful and failed runs on the same benchmark instance",
                "body": "Resolved and unresolved subsets stay aligned to the same task with issue-pull request pairs.",
                "url": "https://example.com/strong",
                "source": "github_repos",
                "query": "pair",
            },
        ]

        sample = gbl._sample_findings(findings, limit=1)

        self.assertEqual(sample[0]["url"], "https://example.com/strong")

    def test_available_platforms_injects_free_web_search_before_premium(self):
        goal_case = {
            "providers": ["exa", "tavily", "github_repos"],
        }
        capability_report = {
            "sources": {
                "searxng": {"status": "ok", "available": True, "runtime_enabled": True, "tier": 0},
                "ddgs": {"status": "ok", "available": True, "runtime_enabled": True, "tier": 0},
                "exa": {"status": "ok", "available": True, "runtime_enabled": True, "tier": 3},
                "tavily": {"status": "ok", "available": True, "runtime_enabled": True, "tier": 3},
                "github_repos": {"status": "ok", "available": True, "runtime_enabled": True, "tier": 1},
            }
        }
        platforms = gbl._available_platforms(goal_case, capability_report)
        self.assertEqual(
            [item["name"] for item in platforms],
            ["searxng", "ddgs", "exa", "tavily", "github_repos"],
        )

    def test_available_platforms_defaults_to_free_web_search_when_no_providers(self):
        capability_report = {
            "sources": {
                "searxng": {"status": "ok", "available": True, "runtime_enabled": True, "tier": 0},
                "ddgs": {"status": "ok", "available": True, "runtime_enabled": True, "tier": 0},
            }
        }
        platforms = gbl._available_platforms({}, capability_report)
        self.assertEqual([item["name"] for item in platforms], ["searxng", "ddgs"])

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

    def test_branch_stale_rounds_counts_recent_rejected_selected_branch(self):
        rounds = [
            {
                "accepted": False,
                "selected_program_id": "p1",
                "candidate_population": [{"program_id": "p1", "branch_id": "repair-a"}],
            },
            {
                "accepted": False,
                "selected_program_id": "p2",
                "candidate_population": [{"program_id": "p2", "branch_id": "repair-a"}],
            },
        ]
        self.assertEqual(gbl._branch_stale_rounds(rounds, "repair-a"), 2)

    def test_population_candidates_can_prefer_diverse_branches(self):
        population = [
            {
                "program_id": "p1",
                "branch_id": "repair-a",
                "score": 80,
                "dimension_scores": {"a": 10},
                "selection": {"weakest_dimension_delta": 1, "repair_alignment": 1, "improved_dimensions": [], "branch_novelty": 1, "family_novelty": 0, "provider_specialization": 0, "repair_depth": 1, "anti_cheat_warnings": []},
                "harness_metrics": {"new_unique_urls": 1},
                "matched_count": 1,
                "finding_count": 5,
                "plan_index": 1,
            },
            {
                "program_id": "p2",
                "branch_id": "repair-a",
                "score": 85,
                "dimension_scores": {"a": 12},
                "selection": {"weakest_dimension_delta": 2, "repair_alignment": 2, "improved_dimensions": ["a"], "branch_novelty": 0, "family_novelty": 0, "provider_specialization": 0, "repair_depth": 1, "anti_cheat_warnings": []},
                "harness_metrics": {"new_unique_urls": 2},
                "matched_count": 1,
                "finding_count": 6,
                "plan_index": 2,
            },
            {
                "program_id": "p3",
                "branch_id": "repair-b",
                "score": 83,
                "dimension_scores": {"a": 11},
                "selection": {"weakest_dimension_delta": 1, "repair_alignment": 1, "improved_dimensions": [], "branch_novelty": 1, "family_novelty": 0, "provider_specialization": 0, "repair_depth": 1, "anti_cheat_warnings": []},
                "harness_metrics": {"new_unique_urls": 1},
                "matched_count": 1,
                "finding_count": 5,
                "plan_index": 3,
            },
        ]
        diverse = gbl._population_candidates(population, prefer_diverse_branches=True)
        self.assertEqual([item["program_id"] for item in diverse], ["p2", "p3"])

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

    def test_promote_compatible_archive_candidate_can_promote_tied_historical_program_without_new_urls(self):
        goal_case = {"id": "goal-x"}
        accepted_program = {"program_id": "seed-program", "queries": [{"text": "seed", "platforms": []}]}
        bundle_state = {
            "accepted_findings": [{"url": "https://a", "title": "a", "source": "github_repos", "query": "seed"}],
            "accepted_queries": [{"text": "seed", "platforms": []}],
            "score": 78,
            "judge": "heuristic-bundle",
            "dimension_scores": {"a": 16, "b": 14, "c": 18, "d": 12, "e": 18},
            "missing_dimensions": [],
            "matched_dimensions": ["a"],
            "rationale": "current",
        }
        archive_payload = {
            "candidate_program": {
                "program_id": "goal-x-r4-c1",
                "parent_program_id": "seed-program",
                "queries": [{"text": "historical query", "platforms": []}],
                "provider_mix": ["searxng", "ddgs"],
            },
            "result": {
                "score": 78,
                "dimension_scores": {"a": 18, "b": 15, "c": 18, "d": 14, "e": 18},
                "harness_metrics": {
                    "total_findings": 36,
                    "new_unique_urls": 0,
                    "novelty_ratio": 0.0,
                    "source_diversity": 0.1,
                    "source_concentration": 0.5,
                    "query_concentration": 0.13,
                },
                "selection": {"current_score": 78},
            },
        }
        promoted_judge = {
            "score": 79,
            "dimension_scores": {"a": 18, "b": 15, "c": 18, "d": 15, "e": 18},
            "missing_dimensions": [],
            "matched_dimensions": ["a", "b", "d"],
            "rationale": "promoted",
            "judge": "heuristic-bundle",
        }
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp) / "program-archive"
            archive_dir.mkdir(parents=True)
            archive_path = archive_dir / "goal-x-r4-c1.json"
            archive_path.write_text(__import__("json").dumps(archive_payload), encoding="utf-8")
            with patch.object(gbl, "runtime_paths", return_value={"program_archive": archive_dir}), \
                 patch.object(gbl, "_replay_queries", return_value=([{"query": "seed"}, {"query": "historical query"}], bundle_state["accepted_findings"])), \
                 patch.object(gbl, "build_bundle", return_value=bundle_state["accepted_findings"]), \
                 patch.object(gbl, "evaluate_goal_bundle", return_value=promoted_judge), \
                 patch.object(gbl, "save_accepted_program") as save_mock:
                program, new_state, judge_result, promoted = gbl._promote_compatible_archive_candidate(
                    goal_case=goal_case,
                    accepted_program=accepted_program,
                    bundle_state=bundle_state,
                    harness={"anti_cheat": {}},
                    platforms=[],
                )
        self.assertEqual(program["program_id"], "goal-x-r4-c1")
        self.assertEqual(new_state["score"], 79)
        self.assertEqual(judge_result["score"], 79)
        self.assertEqual(promoted["selection"]["reason"], "archive_tie_broken_by_profile_or_program")
        save_mock.assert_called_once()

    def test_run_goal_bundle_loop_warm_start_merges_historical_evidence_without_score_regression(self):
        goal_case = {
            "id": "goal-historical-merge",
            "providers": ["github_repos"],
            "dimensions": [{"id": "history", "weight": 20, "keywords": ["historical evidence"]}],
            "target_score": 100,
        }
        accepted_program = {
            "program_id": "seed-program",
            "queries": [{"text": "seed query", "platforms": []}],
            "sampling_policy": {},
            "stop_rules": {},
            "round_roles": ["broad_recall", "dimension_repair"],
            "current_role": "broad_recall",
        }

        class _FakeIndex:
            def __init__(self, path):
                self.records = [{
                    "title": "Historical evidence",
                    "url": "https://example.com/historical",
                    "source": "github_repos",
                    "query": "historical query",
                    "body": "historical evidence",
                }]

            def load_all(self):
                return list(self.records)

            def add(self, records):
                self.records.extend(list(records or []))

        def fake_judge(_goal_case, bundle):
            urls = {item["url"] for item in bundle}
            if "https://example.com/historical" in urls:
                return {
                    "score": 80,
                    "dimension_scores": {"history": 20},
                    "missing_dimensions": [],
                    "matched_dimensions": ["history"],
                    "rationale": "historical evidence preserved",
                    "judge": "heuristic-bundle",
                }
            return {
                "score": 40,
                "dimension_scores": {"history": 10},
                "missing_dimensions": ["history"],
                "matched_dimensions": [],
                "rationale": "replay only",
                "judge": "heuristic-bundle",
            }

        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": goal_case["id"], "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher", return_value=SimpleNamespace(initial_queries=lambda: [], candidate_plans=lambda **kwargs: [])), \
             patch.object(gbl, "load_accepted_program", return_value=accepted_program), \
             patch.object(gbl, "LocalEvidenceIndex", _FakeIndex), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(gbl, "_replay_queries", return_value=(
                 [{"query": "seed query", "query_spec": {"text": "seed query", "platforms": []}, "baseline_score": 5}],
                 [{"title": "Replay evidence", "url": "https://example.com/replay", "source": "github_repos", "query": "seed query"}],
             )), \
             patch.object(gbl, "build_bundle", side_effect=lambda existing, findings, harness: list(findings)), \
             patch.object(gbl, "evaluate_goal_bundle", side_effect=fake_judge), \
             patch.object(
                 gbl,
                 "_promote_compatible_archive_candidate",
                 side_effect=lambda **kwargs: (
                     kwargs["accepted_program"],
                     kwargs["bundle_state"],
                     {
                         "score": kwargs["bundle_state"]["score"],
                         "dimension_scores": kwargs["bundle_state"]["dimension_scores"],
                         "missing_dimensions": kwargs["bundle_state"]["missing_dimensions"],
                         "matched_dimensions": kwargs["bundle_state"].get("matched_dimensions", []),
                         "rationale": kwargs["bundle_state"]["rationale"],
                         "judge": kwargs["bundle_state"]["judge"],
                     },
                     None,
                 ),
             ):
            result = gbl.run_goal_bundle_loop(goal_case, max_rounds=0)

        self.assertEqual(result["bundle_final"]["score"], 80)
        self.assertEqual(result["bundle_final"]["accepted_finding_count"], 2)
        self.assertEqual(result["warm_start"]["replayed_query_count"], 1)

    def test_run_goal_bundle_loop_tracks_query_keyword_hits_for_accepted_rounds(self):
        goal_case = {
            "id": "goal-query-hits",
            "providers": ["github_repos"],
            "dimensions": [
                {"id": "release", "weight": 20, "keywords": ["release gate"]},
                {"id": "validation", "weight": 20, "keywords": ["validation report"]},
            ],
            "target_score": 20,
        }
        saved_programs: list[dict] = []

        def fake_build_candidate_program(**kwargs):
            return {
                "program_id": "goal-query-hits-r1-c1",
                "provider_mix": ["github_repos"],
                "sampling_policy": {},
                "queries": list(kwargs["queries"]),
                "current_role": "dimension_repair",
            }

        def fake_execute(plan, **kwargs):
            queries = list(plan.get("intents") or [])
            return {
                "label": plan.get("label", ""),
                "queries": queries,
                "role": "dimension_repair",
                "branch_type": "repair",
                "branch_subgoal": "",
                "stage": "repair",
                "graph_node": "",
                "graph_edges": [],
                "branch_targets": [],
                "branch_depth": 1,
                "decision": {},
                "planning_ops": [],
                "cross_verification": {"enabled": False, "verification_query_count": 0},
                "deep_steps": [],
                "local_evidence_hits": 0,
                "query_keys": [query["text"] for query in queries],
                "query_runs": [
                    {
                        "query": "release query",
                        "query_spec": {"text": "release query", "platforms": []},
                        "baseline_score": 3,
                        "finding_count": 1,
                        "sample_findings": [],
                    },
                    {
                        "query": "noise query",
                        "query_spec": {"text": "noise query", "platforms": []},
                        "baseline_score": 1,
                        "finding_count": 1,
                        "sample_findings": [],
                    },
                ],
                "findings": [
                    {
                        "title": "Release gate documentation",
                        "body": "A release gate also depends on a validation report.",
                        "url": "https://example.com/release",
                        "source": "github_repos",
                        "query": "release query",
                    },
                    {
                        "title": "Unrelated note",
                        "body": "This does not match the target keywords.",
                        "url": "https://example.com/noise",
                        "source": "github_repos",
                        "query": "noise query",
                    },
                ],
            }

        def fake_synthesize(goal_case, existing_findings, round_findings, harness, graph_plan, gap_queue, planning_ops):
            return {
                "bundle": list(round_findings),
                "judge_result": {
                    "score": 30,
                    "dimension_scores": {"release": 15, "validation": 15},
                    "missing_dimensions": [],
                    "matched_dimensions": ["release", "validation"],
                    "rationale": "accepted",
                    "judge": "heuristic-bundle",
                },
                "harness_metrics": {
                    "total_findings": len(round_findings),
                    "new_unique_urls": len(round_findings),
                    "novelty_ratio": 1.0,
                    "source_diversity": 1.0,
                    "source_concentration": 1.0,
                    "query_concentration": 1.0,
                },
                "routeable_output": {},
                "research_bundle": {},
                "search_graph": {},
                "gap_queue": [],
            }

        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": goal_case["id"], "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(
                 gbl,
                 "GoalSearcher",
                 return_value=SimpleNamespace(
                     initial_queries=lambda: [],
                     candidate_plans=lambda **kwargs: [
                         {
                             "label": "repair",
                             "queries": [
                                 {"text": "release query", "platforms": []},
                                 {"text": "noise query", "platforms": []},
                             ],
                             "program_overrides": {"current_role": "dimension_repair"},
                         }
                     ],
                 ),
             ), \
             patch.object(
                 gbl,
                 "load_accepted_program",
                 return_value={
                     "program_id": "seed-program",
                     "queries": [],
                     "sampling_policy": {},
                     "stop_rules": {},
                     "round_roles": ["dimension_repair"],
                     "current_role": "dimension_repair",
                 },
             ), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(gbl, "build_candidate_program", side_effect=fake_build_candidate_program), \
             patch.object(gbl, "execute_research_plan", side_effect=fake_execute), \
             patch.object(gbl, "synthesize_research_round", side_effect=fake_synthesize), \
             patch.object(gbl, "archive_candidate_program", return_value=Path("/tmp/archive.json")), \
             patch.object(gbl, "save_population_snapshot", return_value={
                 "latest": Path("/tmp/latest.json"),
                 "history": Path("/tmp/history.json"),
                 "latest_lineage": Path("/tmp/latest-lineage.json"),
                 "lineage_history": Path("/tmp/lineage-history.json"),
             }), \
             patch.object(gbl, "candidate_rank", side_effect=lambda item: int(item.get("score") or item["result"]["score"])), \
             patch.object(gbl, "evaluate_acceptance", return_value={"accepted": True, "candidate_score": 30, "anti_cheat_failures": [], "anti_cheat_warnings": []}), \
             patch.object(gbl, "save_accepted_program", side_effect=lambda goal_id, program: saved_programs.append(dict(program))):
            result = gbl.run_goal_bundle_loop(goal_case, max_rounds=1, plan_count_override=1, max_queries_override=2)

        self.assertEqual(result["bundle_final"]["score"], 30)
        self.assertTrue(saved_programs)
        self.assertEqual(
            saved_programs[-1]["query_keyword_hits"],
            {"release query": ["release gate", "validation report"]},
        )

    def test_run_goal_bundle_loop_warm_start_replays_only_queries_with_keyword_hits(self):
        goal_case = {
            "id": "goal-query-filter",
            "providers": ["github_repos"],
            "dimensions": [{"id": "release", "weight": 20, "keywords": ["release gate"]}],
            "target_score": 100,
        }
        accepted_program = {
            "program_id": "seed-program",
            "queries": [
                {"text": "release query", "platforms": []},
                {"text": "validation query", "platforms": []},
                {"text": "discard query", "platforms": []},
            ],
            "query_keyword_hits": {
                "release query": ["release gate"],
                "validation query": ["validation report"],
            },
            "sampling_policy": {},
            "stop_rules": {},
            "round_roles": ["broad_recall", "dimension_repair"],
            "current_role": "broad_recall",
        }
        replayed_queries: list[dict] = []

        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": goal_case["id"], "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher", return_value=SimpleNamespace(initial_queries=lambda: [], candidate_plans=lambda **kwargs: [])), \
             patch.object(gbl, "load_accepted_program", return_value=accepted_program), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(
                 gbl,
                 "_replay_queries",
                 side_effect=lambda queries, platforms, sampling_policy: (
                     replayed_queries.extend(list(queries)),
                     [{"query_spec": query, "baseline_score": 3} for query in queries],
                     [],
                 )[1:],
             ), \
             patch.object(gbl, "build_bundle", side_effect=lambda existing, findings, harness: list(findings)), \
             patch.object(
                 gbl,
                 "evaluate_goal_bundle",
                 return_value={
                     "score": 0,
                     "dimension_scores": {"release": 0},
                     "missing_dimensions": ["release"],
                     "matched_dimensions": [],
                     "rationale": "warm start",
                     "judge": "heuristic-bundle",
                 },
             ), \
             patch.object(
                 gbl,
                 "_promote_compatible_archive_candidate",
                 side_effect=lambda **kwargs: (
                     kwargs["accepted_program"],
                     kwargs["bundle_state"],
                     {
                         "score": kwargs["bundle_state"]["score"],
                         "dimension_scores": kwargs["bundle_state"]["dimension_scores"],
                         "missing_dimensions": kwargs["bundle_state"]["missing_dimensions"],
                         "matched_dimensions": kwargs["bundle_state"].get("matched_dimensions", []),
                         "rationale": kwargs["bundle_state"]["rationale"],
                         "judge": kwargs["bundle_state"]["judge"],
                     },
                     None,
                 ),
             ):
            result = gbl.run_goal_bundle_loop(goal_case, max_rounds=0)

        self.assertEqual([query["text"] for query in replayed_queries], ["release query", "validation query"])
        self.assertEqual(result["warm_start"]["replayed_query_count"], 2)

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
        self.assertIn("gap_queue", result)
        self.assertIn("diary_summary", result)
        self.assertIn("gap_queue", result["rounds"][0])
        self.assertIn("diary_summary", result["rounds"][0])
        self.assertIn("deep_steps", result)
        self.assertIn("deep_steps", result["rounds"][0])

    def test_run_goal_bundle_loop_rotates_strategy_on_plateau_instead_of_stopping(self):
        goal_case = {
            "id": "goal-plateau",
            "providers": ["github_repos"],
            "target_score": 100,
            "dimensions": [{"id": "gap", "weight": 20, "keywords": ["gap"]}],
        }
        built_roles: list[str] = []

        def fake_build_candidate_program(**kwargs):
            current_role = str(kwargs["parent_program"].get("current_role") or "broad_recall")
            built_roles.append(current_role)
            return {
                "program_id": f"goal-plateau-r{kwargs['round_index']}-c{kwargs['candidate_index']}",
                "provider_mix": ["github_repos"],
                "sampling_policy": {},
                "queries": list(kwargs["queries"]),
                "current_role": current_role,
            }

        def fake_execute(plan, **kwargs):
            queries = list(plan.get("intents") or [])
            return {
                "label": plan.get("label", ""),
                "queries": queries,
                "role": str(plan.get("role") or ""),
                "branch_type": "repair",
                "branch_subgoal": "",
                "stage": "repair",
                "graph_node": "",
                "graph_edges": [],
                "branch_targets": [],
                "branch_depth": 1,
                "decision": {},
                "planning_ops": [],
                "cross_verification": {"enabled": False, "verification_query_count": 0},
                "deep_steps": [],
                "local_evidence_hits": 0,
                "query_keys": [query["text"] for query in queries],
                "query_runs": [
                    {
                        "query": queries[0]["text"],
                        "query_spec": queries[0],
                        "baseline_score": 1,
                        "finding_count": 1,
                        "sample_findings": [],
                    }
                ],
                "findings": [{"title": queries[0]["text"], "url": f"https://example.com/{queries[0]['text']}", "source": "github_repos", "query": queries[0]["text"]}],
            }

        def fake_synthesize(goal_case, existing_findings, round_findings, harness, graph_plan, gap_queue, planning_ops):
            return {
                "bundle": list(round_findings),
                "judge_result": {
                    "score": 10,
                    "dimension_scores": {"gap": 10},
                    "missing_dimensions": ["gap"],
                    "matched_dimensions": [],
                    "rationale": "plateau",
                    "judge": "heuristic-bundle",
                },
                "harness_metrics": {
                    "total_findings": len(round_findings),
                    "new_unique_urls": len(round_findings),
                    "novelty_ratio": 1.0,
                    "source_diversity": 1.0,
                    "source_concentration": 1.0,
                    "query_concentration": 1.0,
                },
                "routeable_output": {},
                "research_bundle": {},
                "search_graph": {},
                "gap_queue": [],
            }

        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": "goal-plateau", "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher", return_value=SimpleNamespace(initial_queries=lambda: [], candidate_plans=lambda **kwargs: [])), \
             patch.object(
                 gbl,
                 "load_accepted_program",
                 return_value={
                     "program_id": "seed-program",
                     "queries": [],
                     "sampling_policy": {},
                     "stop_rules": {"plateau_rounds": 1},
                     "plateau_state": {},
                     "round_roles": ["broad_recall", "dimension_repair", "orthogonal_probe"],
                     "current_role": "broad_recall",
                 },
             ), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(
                 gbl,
                 "build_research_plan",
                 side_effect=lambda **kwargs: [
                     {
                         "label": kwargs["active_program"]["current_role"],
                         "queries": [{"text": kwargs["active_program"]["current_role"], "platforms": []}],
                         "program_overrides": {"current_role": kwargs["active_program"]["current_role"]},
                     }
                 ],
             ), \
             patch.object(gbl, "build_candidate_program", side_effect=fake_build_candidate_program), \
             patch.object(gbl, "execute_research_plan", side_effect=fake_execute), \
             patch.object(gbl, "synthesize_research_round", side_effect=fake_synthesize), \
             patch.object(gbl, "archive_candidate_program"), \
             patch.object(gbl, "save_population_snapshot"), \
             patch.object(gbl, "candidate_rank", side_effect=lambda item: int(item.get("score") or 0)), \
             patch.object(gbl, "evaluate_acceptance", return_value={"accepted": False, "candidate_score": 10, "anti_cheat_failures": [], "anti_cheat_warnings": []}), \
             patch.object(gbl, "save_accepted_program"):
            result = gbl.run_goal_bundle_loop(
                goal_case,
                max_rounds=2,
                plan_count_override=1,
                max_queries_override=1,
                plateau_rounds_override=1,
            )
        self.assertEqual(result["stop_reason"], "max_rounds_reached")
        self.assertEqual(len(result["rounds"]), 2)
        self.assertEqual([round_item["round_role"] for round_item in result["rounds"]], ["broad_recall", "dimension_repair"])
        self.assertEqual(built_roles, ["broad_recall", "dimension_repair"])
        self.assertEqual(result["accepted_program"]["current_role"], "orthogonal_probe")
        self.assertIn("stagnant_rounds", result["plateau_state"])

    def test_run_goal_bundle_loop_accepts_target_and_plateau_overrides(self):
        goal_case = {
            "id": "goal-overrides",
            "providers": ["github_repos"],
            "seed_queries": ["seed"],
            "target_score": 60,
            "plateau_rounds": 5,
        }
        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": "goal-overrides", "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher") as searcher_cls, \
             patch.object(gbl, "load_accepted_program", return_value={"program_id": "seed-program", "queries": [], "sampling_policy": {}, "stop_rules": {"plateau_rounds": 5}, "plateau_state": {}}), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(gbl, "_search_query", return_value={"query": "seed", "query_spec": {"text": "seed", "platforms": []}, "baseline_score": 1, "findings": [{"title": "x", "url": "u", "source": "github_repos", "query": "seed"}]}), \
             patch.object(gbl, "build_candidate_program", return_value={"program_id": "goal-overrides-r1-c1", "provider_mix": ["github_repos"], "sampling_policy": {}, "queries": [{"text": "seed", "platforms": []}], "current_role": "broad_recall"}), \
             patch.object(gbl, "archive_candidate_program"), \
             patch.object(gbl, "save_population_snapshot"), \
             patch.object(gbl, "candidate_rank", side_effect=lambda item: int(item.get("score") or 0)), \
             patch.object(gbl, "evaluate_acceptance", return_value={"accepted": False, "candidate_score": 10, "anti_cheat_failures": [], "anti_cheat_warnings": []}), \
             patch.object(gbl, "build_bundle", return_value=[{"title": "x", "url": "u", "source": "github_repos", "query": "seed"}]), \
             patch.object(gbl, "bundle_metrics", return_value={"total_findings": 1, "new_unique_urls": 1, "novelty_ratio": 1.0, "source_diversity": 1.0, "source_concentration": 1.0, "query_concentration": 1.0}), \
             patch.object(gbl, "evaluate_goal_bundle", return_value={"score": 10, "dimension_scores": {"gap": 10}, "missing_dimensions": ["gap"], "matched_dimensions": [], "rationale": "plateau", "judge": "heuristic-bundle"}), \
             patch.object(gbl, "save_accepted_program"):
            searcher_cls.return_value = SimpleNamespace(
                initial_queries=lambda: [{"text": "seed", "platforms": []}],
                candidate_plans=lambda **kwargs: [],
            )
            result = gbl.run_goal_bundle_loop(
                goal_case,
                max_rounds=2,
                plan_count_override=1,
                max_queries_override=1,
                target_score_override=95,
                plateau_rounds_override=1,
            )
        self.assertEqual(result["target_score"], 95)
        self.assertEqual(result["plateau_rounds_limit"], 1)

    def test_run_goal_bundle_loop_surfaces_research_packet_and_deep_steps(self):
        goal_case = {
            "id": "goal-deep-output",
            "providers": ["github_repos"],
            "seed_queries": ["seed"],
            "target_score": 20,
        }
        fake_routeable_output = {
            "goal_id": "goal-deep-output",
            "research_packet": {"packet_id": "packet-1"},
        }
        fake_research_bundle = {"bundle_id": "bundle-1"}
        fake_search_graph = {"deep_loop": {"steps": [{"kind": "search"}]}}
        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": "goal-deep-output", "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher") as searcher_cls, \
             patch.object(gbl, "load_accepted_program", return_value={"program_id": "seed-program", "queries": [], "sampling_policy": {}, "stop_rules": {}, "plateau_state": {}}), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(gbl, "_search_query", return_value={"query": "seed", "query_spec": {"text": "seed", "platforms": []}, "baseline_score": 1, "findings": [{"title": "x", "url": "u", "source": "github_repos", "query": "seed"}]}), \
             patch.object(gbl, "build_candidate_program", return_value={"program_id": "goal-deep-output-r1-c1", "provider_mix": ["github_repos"], "sampling_policy": {}, "queries": [{"text": "seed", "platforms": []}], "current_role": "deep_research"}), \
             patch.object(gbl, "archive_candidate_program"), \
             patch.object(gbl, "save_population_snapshot"), \
             patch.object(gbl, "candidate_rank", side_effect=lambda item: int(item.get("score") or 0)), \
             patch.object(gbl, "evaluate_acceptance", return_value={"accepted": True, "candidate_score": 25, "anti_cheat_failures": [], "anti_cheat_warnings": []}), \
             patch.object(gbl, "build_bundle", return_value=[{"title": "x", "url": "u", "source": "github_repos", "query": "seed"}]), \
             patch.object(gbl, "bundle_metrics", return_value={"total_findings": 1, "new_unique_urls": 1, "novelty_ratio": 1.0, "source_diversity": 1.0, "source_concentration": 1.0, "query_concentration": 1.0}), \
             patch.object(gbl, "evaluate_goal_bundle", return_value={"score": 25, "dimension_scores": {"gap": 25}, "missing_dimensions": [], "matched_dimensions": ["gap"], "rationale": "ok", "judge": "heuristic-bundle"}), \
             patch.object(gbl, "synthesize_research_round", return_value={"bundle": [{"title": "x", "url": "u", "source": "github_repos", "query": "seed"}], "judge_result": {"score": 25, "dimension_scores": {"gap": 25}, "missing_dimensions": [], "matched_dimensions": ["gap"], "rationale": "ok", "judge": "heuristic-bundle"}, "harness_metrics": {"total_findings": 1, "new_unique_urls": 1, "novelty_ratio": 1.0, "source_diversity": 1.0, "source_concentration": 1.0, "query_concentration": 1.0}, "routeable_output": fake_routeable_output, "research_bundle": fake_research_bundle, "search_graph": fake_search_graph, "gap_queue": []}), \
             patch.object(gbl, "save_accepted_program"):
            searcher_cls.return_value = SimpleNamespace(
                initial_queries=lambda: [{"text": "seed", "platforms": []}],
                candidate_plans=lambda **kwargs: [],
            )
            result = gbl.run_goal_bundle_loop(goal_case, max_rounds=1, plan_count_override=1, max_queries_override=1)
        self.assertEqual(result["research_packet"]["packet_id"], "packet-1")
        self.assertEqual(result["rounds"][0]["routeable_output"]["research_packet"]["packet_id"], "packet-1")
        self.assertEqual(result["rounds"][0]["search_graph"]["deep_loop"]["steps"][0]["kind"], "search")

    def test_run_goal_bundle_loop_promotes_accepted_round_artifacts_over_later_rounds(self):
        goal_case = {
            "id": "goal-artifact-selection",
            "providers": ["github_repos"],
            "seed_queries": [],
            "target_score": 100,
        }
        plans = [
            [
                {
                    "label": "accepted-round",
                    "queries": [{"text": "accepted query", "platforms": []}],
                    "program_overrides": {},
                }
            ],
            [
                {
                    "label": "later-round",
                    "queries": [{"text": "later query", "platforms": []}],
                    "program_overrides": {},
                }
            ],
        ]
        executions = [
            {
                "label": "accepted-round",
                "queries": [{"text": "accepted query", "platforms": []}],
                "role": "repair",
                "branch_type": "repair",
                "branch_subgoal": "accepted",
                "stage": "repair",
                "graph_node": "node-1",
                "graph_edges": [],
                "branch_targets": ["accepted"],
                "branch_depth": 1,
                "decision": {"cross_verify": False},
                "planning_ops": [],
                "cross_verification": {"enabled": False, "verification_query_count": 0},
                "deep_steps": [{"kind": "search", "summary": "accepted-round", "metadata": {"round": 1}}],
                "local_evidence_hits": 0,
                "query_keys": ["accepted-query"],
                "query_runs": [
                    {
                        "query": "accepted query",
                        "query_spec": {"text": "accepted query", "platforms": []},
                        "baseline_score": 10,
                        "finding_count": 1,
                        "sample_findings": [],
                    }
                ],
                "findings": [{"title": "accepted", "url": "https://example.com/accepted", "source": "github_repos", "query": "accepted query"}],
            },
            {
                "label": "later-round",
                "queries": [{"text": "later query", "platforms": []}],
                "role": "repair",
                "branch_type": "repair",
                "branch_subgoal": "later",
                "stage": "repair",
                "graph_node": "node-2",
                "graph_edges": [],
                "branch_targets": ["later"],
                "branch_depth": 1,
                "decision": {"cross_verify": False},
                "planning_ops": [],
                "cross_verification": {"enabled": False, "verification_query_count": 0},
                "deep_steps": [{"kind": "search", "summary": "later-round", "metadata": {"round": 2}}],
                "local_evidence_hits": 0,
                "query_keys": ["later-query"],
                "query_runs": [
                    {
                        "query": "later query",
                        "query_spec": {"text": "later query", "platforms": []},
                        "baseline_score": 9,
                        "finding_count": 1,
                        "sample_findings": [],
                    }
                ],
                "findings": [{"title": "later", "url": "https://example.com/later", "source": "github_repos", "query": "later query"}],
            },
        ]
        synthesized = [
            {
                "bundle": [{"title": "accepted", "url": "https://example.com/accepted", "source": "github_repos", "query": "accepted query"}],
                "research_bundle": {"bundle_id": "bundle-accepted"},
                "judge_result": {
                    "score": 40,
                    "dimension_scores": {"artifact_signal": 40},
                    "missing_dimensions": [],
                    "matched_dimensions": ["artifact_signal"],
                    "rationale": "accepted",
                    "judge": "heuristic-bundle",
                },
                "harness_metrics": {"total_findings": 1, "new_unique_urls": 1, "novelty_ratio": 1.0, "source_diversity": 1.0, "source_concentration": 1.0, "query_concentration": 1.0},
                "search_graph": {"deep_loop": {"steps": [{"kind": "search", "summary": "accepted-round"}]}},
                "repair_hints": {},
                "gap_queue": [],
                "routeable_output": {
                    "goal_id": "goal-artifact-selection",
                    "research_packet": {"packet_id": "packet-accepted"},
                    "score_gap": 60,
                },
            },
            {
                "bundle": [{"title": "later", "url": "https://example.com/later", "source": "github_repos", "query": "later query"}],
                "research_bundle": {"bundle_id": "bundle-later"},
                "judge_result": {
                    "score": 35,
                    "dimension_scores": {"artifact_signal": 35},
                    "missing_dimensions": [],
                    "matched_dimensions": ["artifact_signal"],
                    "rationale": "later",
                    "judge": "heuristic-bundle",
                },
                "harness_metrics": {"total_findings": 1, "new_unique_urls": 1, "novelty_ratio": 1.0, "source_diversity": 1.0, "source_concentration": 1.0, "query_concentration": 1.0},
                "search_graph": {"deep_loop": {"steps": [{"kind": "search", "summary": "later-round"}]}},
                "repair_hints": {},
                "gap_queue": [],
                "routeable_output": {
                    "goal_id": "goal-artifact-selection",
                    "research_packet": {"packet_id": "packet-later"},
                    "score_gap": 65,
                },
            },
        ]
        acceptance = iter([
            {"accepted": True, "candidate_score": 40, "anti_cheat_failures": [], "anti_cheat_warnings": []},
            {"accepted": False, "candidate_score": 35, "anti_cheat_failures": [], "anti_cheat_warnings": []},
        ])
        build_program_calls = {"count": 0}
        plan_calls = {"count": 0}
        execution_calls = {"count": 0}
        synth_calls = {"count": 0}

        def fake_build_research_plan(**kwargs):
            index = plan_calls["count"]
            plan_calls["count"] += 1
            return plans[index]

        def fake_build_candidate_program(**kwargs):
            index = build_program_calls["count"]
            build_program_calls["count"] += 1
            return {
                "program_id": f"goal-artifact-selection-r{index + 1}-c1",
                "parent_program_id": "seed-program",
                "provider_mix": ["github_repos"],
                "sampling_policy": {},
                "queries": plans[index][0]["queries"],
                "branch_id": f"branch-{index + 1}",
                "family_id": f"family-{index + 1}",
                "branch_root_program_id": "seed-program",
                "branch_depth": 1,
                "repair_depth": 1,
                "mutation_kind": "dimension_repair",
                "current_role": "repair",
            }

        def fake_execute_research_plan(*args, **kwargs):
            index = execution_calls["count"]
            execution_calls["count"] += 1
            return executions[index]

        def fake_synthesize_research_round(*args, **kwargs):
            index = synth_calls["count"]
            synth_calls["count"] += 1
            return synthesized[index]

        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": "goal-artifact-selection", "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher", return_value=SimpleNamespace(initial_queries=lambda: [], candidate_plans=fake_build_research_plan)), \
             patch.object(gbl, "load_accepted_program", return_value={"program_id": "seed-program", "queries": [], "sampling_policy": {}, "stop_rules": {}, "plateau_state": {}}), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(gbl, "build_research_plan", side_effect=fake_build_research_plan), \
             patch.object(gbl, "build_candidate_program", side_effect=fake_build_candidate_program), \
             patch.object(gbl, "execute_research_plan", side_effect=fake_execute_research_plan), \
             patch.object(gbl, "synthesize_research_round", side_effect=fake_synthesize_research_round), \
             patch.object(gbl, "archive_candidate_program"), \
             patch.object(gbl, "save_population_snapshot"), \
             patch.object(gbl, "candidate_rank", side_effect=lambda item: int(item.get("score") or item["result"]["score"])), \
             patch.object(gbl, "evaluate_acceptance", side_effect=acceptance), \
             patch.object(gbl, "save_accepted_program"):
            result = gbl.run_goal_bundle_loop(goal_case, max_rounds=2, plan_count_override=1, max_queries_override=1)

        self.assertEqual(result["rounds"][0]["routeable_output"]["research_packet"]["packet_id"], "packet-accepted")
        self.assertEqual(result["rounds"][1]["routeable_output"]["research_packet"]["packet_id"], "packet-later")
        self.assertEqual(result["routeable_output"]["research_packet"]["packet_id"], "packet-accepted")
        self.assertEqual(result["research_packet"]["packet_id"], "packet-accepted")
        self.assertEqual(result["deep_steps"][0]["summary"], "accepted-round")
        self.assertEqual(result["rounds"][1]["deep_steps"][0]["summary"], "later-round")

    def test_run_goal_bundle_loop_aligns_routeable_score_gap_with_override_target(self):
        goal_case = {
            "id": "goal-score-gap",
            "providers": ["github_repos"],
            "seed_queries": [],
            "target_score": 100,
        }
        plan = {
            "label": "single-round",
            "queries": [{"text": "single query", "platforms": []}],
            "program_overrides": {},
        }
        execution = {
            "label": "single-round",
            "queries": [{"text": "single query", "platforms": []}],
            "role": "repair",
            "branch_type": "repair",
            "branch_subgoal": "single",
            "stage": "repair",
            "graph_node": "node-1",
            "graph_edges": [],
            "branch_targets": ["single"],
            "branch_depth": 1,
            "decision": {"cross_verify": False},
            "planning_ops": [],
            "cross_verification": {"enabled": False, "verification_query_count": 0},
            "deep_steps": [{"kind": "search", "summary": "single-round", "metadata": {"round": 1}}],
            "local_evidence_hits": 0,
            "query_keys": ["single-query"],
            "query_runs": [
                {
                    "query": "single query",
                    "query_spec": {"text": "single query", "platforms": []},
                    "baseline_score": 10,
                    "finding_count": 1,
                    "sample_findings": [],
                }
            ],
            "findings": [{"title": "single", "url": "https://example.com/single", "source": "github_repos", "query": "single query"}],
        }
        synthesized = {
            "bundle": [{"title": "single", "url": "https://example.com/single", "source": "github_repos", "query": "single query"}],
            "research_bundle": {"bundle_id": "bundle-single"},
            "judge_result": {
                "score": 70,
                "dimension_scores": {"artifact_signal": 70},
                "missing_dimensions": [],
                "matched_dimensions": ["artifact_signal"],
                "rationale": "single",
                "judge": "heuristic-bundle",
            },
            "harness_metrics": {"total_findings": 1, "new_unique_urls": 1, "novelty_ratio": 1.0, "source_diversity": 1.0, "source_concentration": 1.0, "query_concentration": 1.0},
            "search_graph": {"deep_loop": {"steps": [{"kind": "search", "summary": "single-round"}]}},
            "repair_hints": {},
            "gap_queue": [],
            "routeable_output": {
                "goal_id": "goal-score-gap",
                "research_packet": {"packet_id": "packet-single"},
                "score_gap": 30,
            },
        }
        plan_calls = {"count": 0}

        def fake_candidate_plans(**kwargs):
            index = plan_calls["count"]
            plan_calls["count"] += 1
            return [plan] if index == 0 else []

        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": "goal-score-gap", "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher", return_value=SimpleNamespace(initial_queries=lambda: [], candidate_plans=fake_candidate_plans)), \
             patch.object(gbl, "load_accepted_program", return_value={"program_id": "seed-program", "queries": [], "sampling_policy": {}, "stop_rules": {}, "plateau_state": {}}), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(gbl, "build_candidate_program", return_value={
                 "program_id": "goal-score-gap-r1-c1",
                 "parent_program_id": "seed-program",
                 "provider_mix": ["github_repos"],
                 "sampling_policy": {},
                 "queries": plan["queries"],
                 "branch_id": "branch-1",
                 "family_id": "family-1",
                 "branch_root_program_id": "seed-program",
                 "branch_depth": 1,
                 "repair_depth": 1,
                 "mutation_kind": "dimension_repair",
                 "current_role": "repair",
             }), \
             patch.object(gbl, "execute_research_plan", return_value=execution), \
             patch.object(gbl, "synthesize_research_round", return_value=synthesized), \
             patch.object(gbl, "archive_candidate_program"), \
             patch.object(gbl, "save_population_snapshot"), \
             patch.object(gbl, "candidate_rank", side_effect=lambda item: int(item.get("score") or item["result"]["score"])), \
             patch.object(gbl, "evaluate_acceptance", return_value={"accepted": True, "candidate_score": 70, "anti_cheat_failures": [], "anti_cheat_warnings": []}), \
             patch.object(gbl, "save_accepted_program"):
            result = gbl.run_goal_bundle_loop(
                goal_case,
                max_rounds=1,
                plan_count_override=1,
                max_queries_override=1,
                target_score_override=95,
            )

        self.assertEqual(result["score_gap"], 25)
        self.assertEqual(result["routeable_output"]["score_gap"], 25)
        self.assertEqual(result["score_gap"], result["routeable_output"]["score_gap"])

    def test_run_goal_bundle_loop_dedupes_reaccepted_queries(self):
        goal_case = {
            "id": "goal-query-dedupe",
            "providers": ["github_repos"],
            "seed_queries": [],
            "target_score": 100,
        }
        plan = {
            "label": "same-query",
            "queries": [{"text": "repeat query", "platforms": []}],
            "program_overrides": {},
        }
        execution = {
            "label": "same-query",
            "queries": [{"text": "repeat query", "platforms": []}],
            "role": "repair",
            "branch_type": "repair",
            "branch_subgoal": "single",
            "stage": "repair",
            "graph_node": "node-1",
            "graph_edges": [],
            "branch_targets": ["single"],
            "branch_depth": 1,
            "decision": {"cross_verify": False},
            "planning_ops": [],
            "cross_verification": {"enabled": False, "verification_query_count": 0},
            "deep_steps": [{"kind": "search", "summary": "repeat", "metadata": {"round": 1}}],
            "local_evidence_hits": 0,
            "query_keys": ["repeat-query"],
            "query_runs": [
                {
                    "query": "repeat query",
                    "query_spec": {"text": "repeat query", "platforms": []},
                    "baseline_score": 10,
                    "finding_count": 1,
                    "sample_findings": [],
                }
            ],
            "findings": [{"title": "repeat", "url": "https://example.com/repeat", "source": "github_repos", "query": "repeat query"}],
        }
        synthesized = {
            "bundle": [{"title": "repeat", "url": "https://example.com/repeat", "source": "github_repos", "query": "repeat query"}],
            "research_bundle": {"bundle_id": "bundle-repeat"},
            "judge_result": {
                "score": 70,
                "dimension_scores": {"artifact_signal": 70},
                "missing_dimensions": [],
                "matched_dimensions": ["artifact_signal"],
                "rationale": "repeat",
                "judge": "heuristic-bundle",
            },
            "harness_metrics": {"total_findings": 1, "new_unique_urls": 1, "novelty_ratio": 1.0, "source_diversity": 1.0, "source_concentration": 1.0, "query_concentration": 1.0},
            "search_graph": {"deep_loop": {"steps": [{"kind": "search", "summary": "repeat"}]}},
            "repair_hints": {},
            "gap_queue": [],
            "routeable_output": {
                "goal_id": "goal-query-dedupe",
                "research_packet": {"packet_id": "packet-repeat"},
                "score_gap": 30,
            },
        }
        plan_calls = {"count": 0}

        def fake_candidate_plans(**kwargs):
            index = plan_calls["count"]
            plan_calls["count"] += 1
            return [plan] if index < 2 else []

        with patch.object(gbl, "refresh_source_capability", return_value={"sources": {}}), \
             patch.object(gbl, "_available_platforms", return_value=[{"name": "github_repos", "limit": 5}]), \
             patch.object(gbl, "ensure_harness", return_value={"goal_id": "goal-query-dedupe", "bundle_policy": {}, "anti_cheat": {}}), \
             patch.object(gbl, "GoalSearcher", return_value=SimpleNamespace(initial_queries=lambda: [], candidate_plans=lambda **kwargs: [])), \
             patch.object(gbl, "load_accepted_program", return_value={"program_id": "seed-program", "queries": [], "sampling_policy": {}, "stop_rules": {}, "plateau_state": {}}), \
             patch.object(gbl, "_best_prior_run", return_value=(None, None)), \
             patch.object(gbl, "build_research_plan", side_effect=fake_candidate_plans), \
             patch.object(gbl, "build_candidate_program", return_value={
                 "program_id": "goal-query-dedupe-r1-c1",
                 "parent_program_id": "seed-program",
                 "provider_mix": ["github_repos"],
                 "sampling_policy": {},
                 "queries": plan["queries"],
                 "branch_id": "branch-1",
                 "family_id": "family-1",
                 "branch_root_program_id": "seed-program",
                 "branch_depth": 1,
                 "repair_depth": 1,
                 "mutation_kind": "dimension_repair",
                 "current_role": "repair",
             }), \
             patch.object(gbl, "execute_research_plan", return_value=execution), \
             patch.object(gbl, "synthesize_research_round", return_value=synthesized), \
             patch.object(gbl, "archive_candidate_program"), \
             patch.object(gbl, "save_population_snapshot"), \
             patch.object(gbl, "candidate_rank", side_effect=lambda item: int(item.get("score") or item["result"]["score"])), \
             patch.object(gbl, "evaluate_acceptance", return_value={"accepted": True, "candidate_score": 70, "anti_cheat_failures": [], "anti_cheat_warnings": []}), \
             patch.object(gbl, "save_accepted_program"):
            result = gbl.run_goal_bundle_loop(
                goal_case,
                max_rounds=2,
                plan_count_override=1,
                max_queries_override=1,
            )

        self.assertEqual(result["bundle_final"]["accepted_query_count"], 1)
        self.assertEqual(len(result["accepted_program"]["queries"]), 1)


if __name__ == "__main__":
    unittest.main()
