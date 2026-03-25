import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evidence_records import (
    build_evidence_record,
    build_evidence_record_from_result,
    evidence_content_type,
)
from engine import SearchResult


class EvidenceRecordTests(unittest.TestCase):
    def test_build_evidence_record_normalizes_domain_and_content_type(self):
        record = build_evidence_record(
            title="Great Expectations Release Gates",
            url="https://github.com/great-expectations/great_expectations/issues/123",
            body="  Fail closed   release validation   report ",
            source="github_issues",
            query="release validation gate",
        )
        self.assertEqual(record["record_type"], "evidence")
        self.assertEqual(record["domain"], "github.com")
        self.assertEqual(record["content_type"], "issue")
        self.assertEqual(record["snippet"], "Fail closed release validation report")
        self.assertIn("Great Expectations", record["canonical_text"])

    def test_build_evidence_record_from_result_preserves_legacy_fields(self):
        result = SearchResult(
            title="agent eval harness",
            url="https://example.com/harness",
            body="planner executor synthesis",
            source="searxng",
        )
        record = build_evidence_record_from_result(result, "agent eval harness")
        self.assertEqual(record["title"], "agent eval harness")
        self.assertEqual(record["url"], "https://example.com/harness")
        self.assertEqual(record["source"], "searxng")
        self.assertEqual(record["query"], "agent eval harness")

    def test_evidence_content_type_detects_dataset_urls(self):
        self.assertEqual(
            evidence_content_type("huggingface_datasets", "https://huggingface.co/datasets/example/data"),
            "dataset",
        )


if __name__ == "__main__":
    unittest.main()
