import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from acquisition import enrich_evidence_record, extract_visible_text
from goal_services import search_query
from engine import PlatformSearchOutcome, SearchResult


class AcquisitionTests(unittest.TestCase):
    def test_extract_visible_text_skips_script_and_style(self):
        html = """
        <html>
          <head>
            <title>Agent Eval Harness</title>
            <style>.hidden { display:none }</style>
            <script>console.log('ignore')</script>
          </head>
          <body>
            <h1>Planner Executor Report</h1>
            <p>Structured evidence extraction.</p>
          </body>
        </html>
        """
        extracted = extract_visible_text(html)
        self.assertEqual(extracted["title"], "Agent Eval Harness")
        self.assertIn("Planner Executor Report", extracted["text"])
        self.assertNotIn("console.log", extracted["text"])

    def test_enrich_evidence_record_adds_acquired_fields(self):
        with patch("acquisition.fetch_page", return_value={
            "title": "Fetched Title",
            "text": "Clean extracted page text",
            "content_type": "text/html",
        }):
            enriched = enrich_evidence_record({"url": "https://example.com"})
        self.assertTrue(enriched["acquired"])
        self.assertEqual(enriched["acquired_title"], "Fetched Title")
        self.assertEqual(enriched["acquired_text"], "Clean extracted page text")
        self.assertIn("chunk_scores", enriched)
        self.assertIn("selected_chunks", enriched)

    def test_search_query_optionally_enriches_page_records(self):
        outcome = PlatformSearchOutcome(
            provider="searxng",
            results=[
                SearchResult(
                    title="Harness engineering",
                    url="https://example.com/harness",
                    body="planner executor synthesizer",
                    source="searxng",
                )
            ],
        )
        with patch("goal_services.PlatformConnector.search", return_value=outcome), \
             patch("goal_services.enrich_evidence_record", side_effect=lambda record: dict(record, acquired=True, acquired_text="fetched")):
            run = search_query(
                "harness engineering",
                [{"name": "searxng", "limit": 5}],
                sampling_policy={"acquire_pages": True, "page_fetch_limit": 1},
            )
        self.assertEqual(len(run["findings"]), 1)
        self.assertTrue(run["findings"][0]["acquired"])
        self.assertEqual(run["findings"][0]["acquired_text"], "fetched")


if __name__ == "__main__":
    unittest.main()
