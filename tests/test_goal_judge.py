import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import goal_judge as gj


class GoalJudgeTests(unittest.TestCase):
    def test_heuristic_bundle_eval_returns_keyword_hits_and_misses(self):
        goal_case = {
            "dimensions": [
                {
                    "id": "dedupe_quality",
                    "weight": 20,
                    "keywords": [
                        "semantic deduplication",
                        "near duplicate detection",
                        "fake gold",
                    ],
                    "aliases": ["duplicate detection"],
                }
            ]
        }
        findings = [
            {
                "title": "Semantic deduplication implementation details",
                "body": "Production notes for semantic deduplication in a retrieval pipeline.",
                "url": "https://example.com/dedupe",
                "source": "github_repos",
            }
        ]

        result = gj.evaluate_goal_bundle(goal_case, findings)

        self.assertEqual(
            result["dimension_keyword_hits"]["dedupe_quality"],
            ["semantic deduplication"],
        )
        self.assertEqual(
            result["dimension_keyword_misses"]["dedupe_quality"],
            ["near duplicate detection", "fake gold", "duplicate detection"],
        )

    def test_heuristic_bundle_eval_uses_rubric_when_dimensions_missing(self):
        goal_case = {
            "rubric": [
                {
                    "id": "provider_skip",
                    "weight": 35,
                    "keywords": ["skip unavailable provider", "provider cooldown"],
                },
                {
                    "id": "doctor",
                    "weight": 35,
                    "keywords": ["doctor report", "capability check"],
                },
            ]
        }
        findings = [
            {
                "title": "Provider cooldown and skip unavailable provider",
                "url": "u1",
                "source": "github_issues",
            },
            {
                "title": "Doctor report for capability check",
                "url": "u2",
                "source": "github_repos",
            },
        ]
        result = gj.evaluate_goal_bundle(goal_case, findings)
        self.assertGreaterEqual(result["score"], 35)
        self.assertIn("provider_skip", result["dimension_scores"])
        self.assertIn("doctor", result["dimension_scores"])

    def test_heuristic_goal_judge_scores_matching_rubric(self):
        goal_case = {
            "rubric": [
                {"id": "metric", "weight": 20, "keywords": ["score", "rubric"]},
                {"id": "judge", "weight": 20, "keywords": ["judge", "evaluator"]},
                {"id": "selection", "weight": 20, "keywords": ["keep", "discard"]},
            ]
        }
        findings = [
            {
                "title": "A judge loop with explicit score rubric and keep discard selection",
                "url": "https://example.com/repo",
                "body": "Implementation details for evaluator driven iteration.",
                "source": "exa",
            }
        ]
        result = gj.HeuristicGoalJudge().evaluate(goal_case, "judge loop", findings)

        self.assertGreaterEqual(result["score"], 40)
        self.assertIn("score", result["matched_terms"])
        self.assertIn("judge", result["matched_terms"])
        self.assertEqual(result["judge"], "heuristic")

    def test_heuristic_bundle_does_not_under_score_semantic_cross_project_evidence(
        self,
    ):
        goal_case = {
            "dimensions": [
                {
                    "id": "label_separation",
                    "weight": 20,
                    "keywords": [
                        "validation after extraction",
                        "separate extraction and validation",
                        "filter later",
                    ],
                }
            ]
        }
        findings = [
            {
                "title": "A data pipeline that keeps extraction and QA in different stages",
                "body": "The system extracts records first, then applies validation and labeling as a later pass.",
                "url": "https://example.com/pipeline",
                "source": "github_repos",
            },
            {
                "title": "Post-processing gates enforce schema checks after ingestion",
                "body": "Validation is deferred until after the raw extraction step finishes.",
                "url": "https://example.org/gates",
                "source": "huggingface_datasets",
            },
        ]
        result = gj.evaluate_goal_bundle(goal_case, findings)

        self.assertGreaterEqual(result["dimension_scores"]["label_separation"], 10)
        self.assertIn("label_separation", result["matched_dimensions"])

    def test_pair_extract_scores_public_pair_trajectory_vocabulary(self):
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
                    "aliases": [
                        "issue pull request pair",
                        "same benchmark instance",
                        "successful and failed runs",
                        "resolved unresolved subset",
                        "verified trajectories",
                    ],
                }
            ]
        }
        findings = [
            {
                "title": "Verified trajectories include successful and failed runs on the same benchmark instance",
                "body": "The benchmark release keeps resolved and unresolved subsets aligned to the same task, with issue-pull request pairs and trace records for both outcomes.",
                "url": "https://example.com/verified-trajectories",
                "source": "github_repos",
            },
            {
                "title": "Dataset card for paired issue-pull request trajectories",
                "body": "Each benchmark instance links successful and failed runs to the same task identifier.",
                "url": "https://example.org/dataset-card",
                "source": "huggingface_datasets",
            },
        ]
        result = gj.evaluate_goal_bundle(goal_case, findings)

        self.assertGreaterEqual(result["dimension_scores"]["pair_extract"], 10)
        self.assertIn("pair_extract", result["matched_dimensions"])

    def test_pair_extract_reports_structural_detail(self):
        goal_case = {
            "dimensions": [
                {
                    "id": "pair_extract",
                    "weight": 20,
                    "keywords": [
                        "SWE-bench",
                        "trajectory",
                        "SWE-agent",
                        "resolved",
                        "unresolved",
                        "success failure",
                    ],
                    "aliases": [
                        "same benchmark instance",
                        "successful and failed runs",
                        "verified trajectories",
                        "same task",
                    ],
                }
            ]
        }
        findings = [
            {
                "title": "Verified trajectories include successful and failed runs on the same benchmark instance",
                "body": "Resolved and unresolved subsets are aligned to the same task with issue-pull request artifacts.",
                "url": "https://example.com/pair-proof",
                "source": "github_repos",
            }
        ]

        result = gj.evaluate_goal_bundle(goal_case, findings)

        detail = result.get("pair_extract_detail")
        self.assertIsInstance(detail, dict)
        self.assertTrue(detail.get("shared_unit"))
        self.assertTrue(detail.get("dual_outcome"))
        self.assertTrue(detail.get("trajectory_form"))
        self.assertTrue(detail.get("artifact_link"))
        self.assertIn(
            "https://example.com/pair-proof", list(detail.get("supporting_urls") or [])
        )

    def test_pair_extract_structural_signals_raise_score_beyond_token_floor(self):
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
                    "aliases": [
                        "issue pull request pair",
                        "same benchmark instance",
                        "successful and failed runs",
                        "resolved unresolved subset",
                        "verified trajectories",
                        "same task",
                    ],
                }
            ]
        }
        findings = [
            {
                "title": "Benchmark artifact attaches passing and failing traces to the same task identifier",
                "body": "The dataset links both outcomes back to the same task identifier and keeps pull request artifacts for every run trace.",
                "url": "https://example.com/structural",
                "source": "huggingface_datasets",
            }
        ]

        result = gj.evaluate_goal_bundle(goal_case, findings)

        self.assertTrue(result["pair_extract_detail"]["shared_unit"])
        self.assertTrue(result["pair_extract_detail"]["dual_outcome"])
        self.assertTrue(result["pair_extract_detail"]["trajectory_form"])
        self.assertTrue(result["pair_extract_detail"]["artifact_link"])
        self.assertGreaterEqual(result["dimension_scores"]["pair_extract"], 16)

    def test_openrouter_bundle_eval_does_not_silently_fallback_in_strict_mode(self):
        with patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "x", "OPENROUTER_STRICT_JUDGE": "1"},
            clear=False,
        ):
            with patch.object(
                gj, "_openrouter_bundle_eval", side_effect=RuntimeError("timeout")
            ):
                with self.assertRaises(RuntimeError):
                    gj.evaluate_goal_bundle({"dimensions": []}, [])

    def test_openrouter_bundle_eval_can_fallback_when_strict_mode_disabled(self):
        with patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "x", "OPENROUTER_STRICT_JUDGE": "0"},
            clear=False,
        ):
            with patch.object(
                gj, "_openrouter_bundle_eval", side_effect=RuntimeError("timeout")
            ):
                result = gj.evaluate_goal_bundle({"dimensions": []}, [])
        self.assertEqual(result["judge"], "heuristic-bundle")

    def test_openrouter_bundle_eval_uses_rubric_dimensions_when_explicit_dimensions_missing(
        self,
    ):
        goal_case = {
            "problem": "doctor loop",
            "rubric": [
                {"id": "runtime_skip", "weight": 20, "keywords": ["skip", "runtime"]},
                {"id": "doctor", "weight": 20, "keywords": ["doctor", "health"]},
            ],
        }

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return BytesIO(
                    b'{"choices":[{"message":{"content":"{\\"score\\": 27, \\"dimension_scores\\": {\\"doctor\\": 12}, \\"matched_dimensions\\": [\\"doctor\\"], \\"missing_dimensions\\": [], \\"rationale\\": \\"ok\\"}"}}]}'
                ).read()

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "x"}, clear=False):
            with patch.object(
                gj.urllib.request, "urlopen", return_value=_FakeResponse()
            ) as mocked:
                result = gj.evaluate_goal_bundle(
                    goal_case,
                    [{"title": "doctor health report", "url": "u", "source": "exa"}],
                )

        request = mocked.call_args.args[0]
        prompt = json.loads(request.data.decode("utf-8"))["messages"][0]["content"]
        self.assertIn('"id": "runtime_skip"', prompt)
        self.assertIn('"id": "doctor"', prompt)
        self.assertEqual(result["dimension_scores"]["runtime_skip"], 0)
        self.assertEqual(result["dimension_scores"]["doctor"], 12)
        self.assertIn("runtime_skip", result["missing_dimensions"])

    def test_bundle_sample_includes_rich_content(self):
        findings = [
            {
                "title": "Repo A",
                "url": "https://a.com",
                "source": "github_repos",
                "query": "test query",
                "body": "short snippet",
                "fit_markdown": "x" * 2400,
            },
            {
                "title": "Repo B",
                "url": "https://b.com",
                "source": "github_repos",
                "query": "test query",
                "body": "another snippet",
            },
        ]
        sample = gj._bundle_sample(findings, limit=5)
        self.assertEqual(len(sample), 2)
        item_a = sample[0]
        self.assertIn("content", item_a)
        self.assertEqual(len(item_a["content"]), 1500)
        item_b = sample[1]
        self.assertNotIn("content", item_b)

    def test_dimension_aware_sample_covers_all_dimensions(self):
        dimensions = [
            {"id": "dim_a", "weight": 20, "keywords": ["alpha"]},
            {"id": "dim_b", "weight": 20, "keywords": ["beta"]},
            {"id": "dim_c", "weight": 20, "keywords": ["gamma"]},
        ]
        findings = []
        for i in range(10):
            findings.append(
                {
                    "title": f"alpha doc {i}",
                    "url": f"https://a.com/{i}",
                    "body": "alpha content",
                    "source": "github_repos",
                    "query": "q1",
                }
            )
        findings.append(
            {
                "title": "beta doc",
                "url": "https://b.com/0",
                "body": "beta content",
                "source": "github_repos",
                "query": "q2",
            }
        )
        findings.append(
            {
                "title": "gamma doc",
                "url": "https://c.com/0",
                "body": "gamma content",
                "source": "github_repos",
                "query": "q3",
            }
        )
        sample = gj._dimension_aware_bundle_sample(findings, dimensions, limit=9)
        urls = [item["url"] for item in sample]
        self.assertIn("https://b.com/0", urls)
        self.assertIn("https://c.com/0", urls)
        self.assertLessEqual(len(sample), 9)

    def test_dimension_aware_sample_includes_content(self):
        dimensions = [
            {"id": "dim_a", "weight": 20, "keywords": ["alpha"]},
        ]
        findings = [
            {
                "title": "alpha doc",
                "url": "https://a.com",
                "body": "short",
                "source": "github_repos",
                "fit_markdown": "rich alpha content " * 100,
            }
        ]
        sample = gj._dimension_aware_bundle_sample(findings, dimensions, limit=5)
        self.assertEqual(len(sample), 1)
        self.assertIn("content", sample[0])
        self.assertLessEqual(len(sample[0]["content"]), 1500)

    def test_dimension_aware_sample_falls_back_without_dimensions(self):
        findings = [
            {
                "title": "doc",
                "url": "https://a.com",
                "body": "content",
                "source": "github_repos",
                "query": "q",
            }
        ]
        sample = gj._dimension_aware_bundle_sample(findings, [], limit=5)
        self.assertEqual(len(sample), 1)

    def test_evaluate_goal_bundle_accepts_explicit_research_bundle_payload(self):
        goal_case = {
            "rubric": [
                {"id": "doctor", "weight": 20, "keywords": ["doctor", "health"]},
            ]
        }
        bundle = {
            "goal_id": "doctor-goal",
            "bundle_id": "bundle-1",
            "evidence_records": [
                {"title": "doctor health report", "url": "u", "source": "searxng"},
            ],
        }
        result = gj.evaluate_goal_bundle(goal_case, bundle)
        self.assertIn("doctor", result["dimension_scores"])


if __name__ == "__main__":
    unittest.main()
