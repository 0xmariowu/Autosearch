import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from acquisition import AcquiredDocument
from acquisition.fetch_pipeline import fetch_document


class AcquisitionPipelineTests(unittest.TestCase):
    def test_fetch_document_builds_markdown_and_references(self):
        html = """
        <html>
          <head><title>Eval Harness</title></head>
          <body>
            <a href="/docs">Docs</a>
            <p>Planner executor synthesizer</p>
          </body>
        </html>
        """
        with patch("acquisition.fetch_pipeline.fetch_page", return_value={
            "url": "https://example.com",
            "final_url": "https://example.com",
            "content_type": "text/html",
            "raw_html": html,
        }):
            document = fetch_document("https://example.com")
        self.assertEqual(document.title, "Eval Harness")
        self.assertIn("Planner executor synthesizer", document.clean_markdown)
        self.assertTrue(document.fit_markdown)
        self.assertEqual(document.references[0]["url"], "https://example.com/docs")

    def test_fetch_document_can_use_render_fallback(self):
        fallback_doc = AcquiredDocument(
            url="https://example.com",
            final_url="https://example.com",
            content_type="text/html",
            title="Rendered",
            text="rendered text",
            raw_html="<html></html>",
            used_render_fallback=True,
        )
        with patch("acquisition.fetch_pipeline.fetch_page", side_effect=RuntimeError("boom")), \
             patch("acquisition.fetch_pipeline.render_document", return_value=fallback_doc):
            document = fetch_document("https://example.com", use_render_fallback=True)
        self.assertTrue(document.used_render_fallback)
        self.assertEqual(document.title, "Rendered")


if __name__ == "__main__":
    unittest.main()
