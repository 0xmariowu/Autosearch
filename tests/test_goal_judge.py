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
    def test_heuristic_bundle_eval_uses_rubric_when_dimensions_missing(self):
        goal_case = {
            "rubric": [
                {"id": "provider_skip", "weight": 35, "keywords": ["skip unavailable provider", "provider cooldown"]},
                {"id": "doctor", "weight": 35, "keywords": ["doctor report", "capability check"]},
            ]
        }
        findings = [
            {"title": "Provider cooldown and skip unavailable provider", "url": "u1", "source": "github_issues"},
            {"title": "Doctor report for capability check", "url": "u2", "source": "github_repos"},
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

    def test_openrouter_bundle_eval_does_not_silently_fallback_in_strict_mode(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "x", "OPENROUTER_STRICT_JUDGE": "1"}, clear=False):
            with patch.object(gj, "_openrouter_bundle_eval", side_effect=RuntimeError("timeout")):
                with self.assertRaises(RuntimeError):
                    gj.evaluate_goal_bundle({"dimensions": []}, [])

    def test_openrouter_bundle_eval_can_fallback_when_strict_mode_disabled(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "x", "OPENROUTER_STRICT_JUDGE": "0"}, clear=False):
            with patch.object(gj, "_openrouter_bundle_eval", side_effect=RuntimeError("timeout")):
                result = gj.evaluate_goal_bundle({"dimensions": []}, [])
        self.assertEqual(result["judge"], "heuristic-bundle")

    def test_openrouter_bundle_eval_uses_rubric_dimensions_when_explicit_dimensions_missing(self):
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
            with patch.object(gj.urllib.request, "urlopen", return_value=_FakeResponse()) as mocked:
                result = gj.evaluate_goal_bundle(goal_case, [{"title": "doctor health report", "url": "u", "source": "exa"}])

        request = mocked.call_args.args[0]
        prompt = json.loads(request.data.decode("utf-8"))["messages"][0]["content"]
        self.assertIn('"id": "runtime_skip"', prompt)
        self.assertIn('"id": "doctor"', prompt)
        self.assertEqual(result["dimension_scores"]["runtime_skip"], 0)
        self.assertEqual(result["dimension_scores"]["doctor"], 12)
        self.assertIn("runtime_skip", result["missing_dimensions"])


if __name__ == "__main__":
    unittest.main()
