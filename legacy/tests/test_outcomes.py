import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import outcomes


class OutcomesProvenanceTests(unittest.TestCase):
    def test_find_source_provenance_prefers_harvested_urls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            evolution_path = Path(tmpdir) / "evolution.jsonl"
            evolution_path.write_text(
                json.dumps(
                    {
                        "query": "AI coding agent",
                        "query_family": "coding-agent",
                        "harvested_urls": ["github.com/example/repo"],
                        "sample_titles": ["example/repo issue thread"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(outcomes, "EVOLUTION_PATH", evolution_path):
                provenance = outcomes._load_query_provenance()

            query, query_family = outcomes._find_source_provenance(
                "github.com/example/repo",
                {},
                provenance,
            )

            self.assertEqual(query, "AI coding agent")
            self.assertEqual(query_family, "coding-agent")


if __name__ == "__main__":
    unittest.main()
