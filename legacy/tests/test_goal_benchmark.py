import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_benchmark import _benchmark_summary, run_benchmark


class GoalBenchmarkTests(unittest.TestCase):
    def test_benchmark_summary_extracts_core_fields(self):
        summary = _benchmark_summary(
            {
                "goal_id": "goal-x",
                "problem": "test problem",
                "target_score": 80,
                "providers_used": ["github_repos"],
                "accepted_program": {"program_id": "prog-1"},
                "bundle_final": {
                    "score": 72,
                    "matched_dimensions": ["a"],
                    "missing_dimensions": ["b"],
                },
                "rounds": [
                    {"accepted": True},
                    {"accepted": False},
                ],
            }
        )
        self.assertEqual(summary["goal_id"], "goal-x")
        self.assertEqual(summary["final_score"], 72)
        self.assertFalse(summary["goal_reached"])
        self.assertEqual(summary["score_gap"], 8)
        self.assertEqual(summary["accepted_rounds"], 1)
        self.assertEqual(summary["accepted_program_id"], "prog-1")

    def test_run_benchmark_forwards_target_controls(self):
        goal_path = Path("/tmp/goal-a.json")
        with (
            unittest.mock.patch(
                "goal_benchmark.load_goal_case", return_value={"id": "goal-a"}
            ),
            unittest.mock.patch(
                "goal_benchmark.run_goal_bundle_loop",
                return_value={
                    "goal_id": "goal-a",
                    "problem": "p",
                    "target_score": 100,
                    "goal_reached": False,
                    "score_gap": 90,
                    "stop_reason": "plateau_detected",
                    "practical_ceiling": 10,
                    "providers_used": [],
                    "accepted_program": {"program_id": "p1"},
                    "bundle_final": {
                        "score": 10,
                        "matched_dimensions": [],
                        "missing_dimensions": [],
                    },
                    "rounds": [],
                },
            ) as mocked_loop,
        ):
            result = run_benchmark([goal_path], 2, target_score=100, plateau_rounds=2)
        self.assertEqual(result["payload"]["target_score"], 100)
        self.assertEqual(result["payload"]["plateau_rounds"], 2)
        self.assertEqual(mocked_loop.call_args.kwargs["target_score_override"], 100)
        self.assertEqual(mocked_loop.call_args.kwargs["plateau_rounds_override"], 2)


if __name__ == "__main__":
    unittest.main()
