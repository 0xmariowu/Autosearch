import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_runtime import default_program
from research.mode_policy import apply_mode_policy
from research.modes import get_mode_policy


class ModePolicyTests(unittest.TestCase):
    def test_speed_mode_policy_is_lightweight(self):
        policy = get_mode_policy("speed")
        self.assertFalse(policy.enable_acquisition)
        self.assertEqual(policy.max_plan_count, 1)

    def test_deep_mode_policy_enables_acquisition_and_depth(self):
        policy = get_mode_policy("deep")
        self.assertTrue(policy.enable_acquisition)
        self.assertGreaterEqual(policy.max_branch_depth, 5)

    def test_default_program_applies_mode_policy(self):
        program = default_program({"id": "goal-a", "mode": "deep"}, ["searxng", "github_repos"])
        self.assertEqual(program["mode"], "deep")
        self.assertTrue(program["acquisition_policy"]["acquire_pages"])
        self.assertGreaterEqual(program["plan_count"], 5)

    def test_apply_mode_policy_preserves_overrides(self):
        updated = apply_mode_policy({
            "mode": "balanced",
            "acquisition_policy": {"acquire_pages": True, "page_fetch_limit": 4},
            "sampling_policy": {},
            "evidence_policy": {},
            "repair_policy": {},
            "population_policy": {},
        })
        self.assertTrue(updated["acquisition_policy"]["acquire_pages"])
        self.assertGreaterEqual(updated["acquisition_policy"]["page_fetch_limit"], 4)


if __name__ == "__main__":
    unittest.main()
