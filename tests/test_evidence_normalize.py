import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from acquisition import AcquiredDocument
from evidence.legacy_adapter import normalize_legacy_finding
from evidence.normalize import normalize_acquired_document, normalize_result_record
from engine import SearchResult


class EvidenceNormalizeTests(unittest.TestCase):
    def test_normalize_result_record_builds_evidence(self):
        record = normalize_result_record(
            SearchResult(
                title="Great Expectations gate",
                url="https://github.com/example/project/issues/1",
                body="fail closed validation release gate",
                source="github_issues",
            ),
            "validation gate",
        )
        self.assertEqual(record["record_type"], "evidence")
        self.assertEqual(record["content_type"], "issue")

    def test_normalize_acquired_document_includes_markdown(self):
        document = AcquiredDocument(
            url="https://example.com",
            final_url="https://example.com",
            content_type="text/html",
            title="Research Page",
            text="Visible text",
            clean_markdown="Visible text",
            fit_markdown="Visible text",
            references=[{"url": "https://example.com/ref"}],
        )
        record = normalize_acquired_document(document, source="searxng", query="research page")
        self.assertEqual(record["fit_markdown"], "Visible text")
        self.assertEqual(record["references"][0]["url"], "https://example.com/ref")

    def test_normalize_legacy_finding_keeps_old_shapes_working(self):
        record = normalize_legacy_finding({
            "title": "legacy",
            "url": "https://example.com",
            "body": "legacy body",
            "source": "searxng",
            "query": "legacy query",
        })
        self.assertEqual(record["record_type"], "evidence")
        self.assertEqual(record["query"], "legacy query")


if __name__ == "__main__":
    unittest.main()
