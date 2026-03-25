import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import goal_runtime as gr


class GoalRuntimeTests(unittest.TestCase):
    def test_default_program_uses_seed_queries(self):
        program = gr.default_program(
            {"id": "g1", "seed_queries": ["a", {"text": "b", "platforms": []}]},
            ["github_repos"],
        )
        self.assertEqual(program["program_id"], "seed-program")
        self.assertEqual([item["text"] for item in program["queries"]], ["a", "b"])

    def test_ensure_harness_persists_default_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp)
            with patch.object(gr, "GOAL_RUNTIME_ROOT", runtime_root):
                harness = gr.ensure_harness({"id": "goal-x"})
                self.assertEqual(harness["goal_id"], "goal-x")
                saved = gr.runtime_paths("goal-x")["harness"]
                self.assertTrue(saved.exists())


if __name__ == "__main__":
    unittest.main()
