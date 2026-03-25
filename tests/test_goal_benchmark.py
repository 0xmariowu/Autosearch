import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_benchmark import _benchmark_summary


class GoalBenchmarkTests(unittest.TestCase):
    def test_benchmark_summary_extracts_core_fields(self):
        summary = _benchmark_summary({
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
        })
        self.assertEqual(summary["goal_id"], "goal-x")
        self.assertEqual(summary["final_score"], 72)
        self.assertEqual(summary["accepted_rounds"], 1)
        self.assertEqual(summary["accepted_program_id"], "prog-1")


if __name__ == "__main__":
    unittest.main()
