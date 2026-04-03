import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evidence_index import LocalEvidenceIndex, search_evidence


class EvidenceIndexTests(unittest.TestCase):
    def test_local_index_adds_and_dedupes_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index = LocalEvidenceIndex(Path(tmpdir) / "evidence.jsonl")
            added = index.add(
                [
                    {
                        "title": "Eval Harness",
                        "url": "https://example.com/a",
                        "canonical_text": "planner executor",
                    },
                    {
                        "title": "Eval Harness",
                        "url": "https://example.com/a",
                        "canonical_text": "planner executor",
                    },
                ]
            )
            self.assertEqual(added, 1)
            self.assertEqual(len(index.load_all()), 1)

    def test_search_evidence_ranks_matching_records(self):
        records = [
            {
                "title": "Harness Engineering",
                "canonical_text": "planner executor synthesis",
                "source": "searxng",
            },
            {
                "title": "Release Gates",
                "canonical_text": "fail closed validation report",
                "source": "github_issues",
            },
        ]
        results = search_evidence(records, "planner synthesis", limit=5)
        self.assertEqual(results[0]["title"], "Harness Engineering")


if __name__ == "__main__":
    unittest.main()
