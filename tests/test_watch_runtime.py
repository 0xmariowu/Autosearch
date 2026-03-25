import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from watch.models import GoalWatch
from watch.runtime import run_watch, run_watches


class WatchRuntimeTests(unittest.TestCase):
    def test_goal_watch_from_mapping(self):
        watch = GoalWatch.from_mapping({"goal_id": "goal-a", "mode": "deep"})
        self.assertEqual(watch.watch_id, "goal-a")
        self.assertEqual(watch.mode, "deep")

    def test_run_watch_forwards_mode_and_budget(self):
        def resolve_goal_case(goal_id):
            return {"id": goal_id, "mode": "balanced"}

        def optimize_goal(goal_case, **kwargs):
            return {"bundle_final": {"score": 88}, "goal_case": goal_case, "kwargs": kwargs}

        result = run_watch(
            {"goal_id": "goal-a", "mode": "deep", "budget": {"rounds": 4, "plan_count": 2, "max_queries": 3}},
            resolve_goal_case=resolve_goal_case,
            optimize_goal=optimize_goal,
        )
        self.assertEqual(result["mode"], "deep")
        self.assertEqual(result["final_score"], 88)
        self.assertFalse(result["goal_reached"])

    def test_run_watches_aggregates_results(self):
        payload = run_watches(
            [{"goal_id": "goal-a"}, {"goal_id": "goal-b"}],
            resolve_goal_case=lambda goal_id: {"id": goal_id},
            optimize_goal=lambda goal_case, **kwargs: {"bundle_final": {"score": 100}},
        )
        self.assertEqual(payload["watch_count"], 2)


if __name__ == "__main__":
    unittest.main()
