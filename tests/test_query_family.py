import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from daily import extract_query_family_maps
from engine import Engine, EngineConfig


class QueryFamilyTests(unittest.TestCase):
    def test_word_vote_infers_family_for_generated_query(self):
        data = {
            "topic_groups": [
                {
                    "id": "coding-agent",
                    "queries": {
                        "github": ["AI coding agent", "autonomous coding tool"],
                    },
                },
                {
                    "id": "mcp",
                    "queries": {
                        "github": ["model context protocol server"],
                    },
                },
            ]
        }
        query_family_map, word_map = extract_query_family_maps(data)
        engine = Engine(
            EngineConfig(
                query_family_map=query_family_map,
                query_family_word_map=word_map,
            ),
            REPO_ROOT,
        )

        self.assertEqual(engine._query_family_for_query("AI coding agent"), "coding-agent")
        self.assertEqual(engine._query_family_for_query("best coding tool"), "coding-agent")
        self.assertEqual(engine._query_family_for_query("protocol server patterns"), "mcp")


if __name__ == "__main__":
    unittest.main()
