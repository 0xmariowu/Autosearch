import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from acquisition import AcquiredDocument
from acquisition.chunking import chunk_document
from acquisition.content_filter import select_relevant_content
from acquisition.crawl4ai_adapter import fetch_with_crawl4ai
from acquisition.fetch_pipeline import fetch_document
from acquisition.markdown_strategy import build_markdown_views
from acquisition.render_pipeline import render_document


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
        with patch(
            "acquisition.fetch_pipeline.fetch_page",
            return_value={
                "url": "https://example.com",
                "final_url": "https://example.com",
                "status_code": 200,
                "content_type": "text/html",
                "raw_html": html,
            },
        ):
            document = fetch_document("https://example.com")
        self.assertTrue(document.document_id)
        self.assertEqual(document.status_code, 200)
        self.assertEqual(document.fetch_method, "http_fetch")
        self.assertEqual(document.metadata["pipeline"], "native")
        self.assertEqual(document.title, "Eval Harness")
        self.assertIn("Planner executor synthesizer", document.clean_markdown)
        self.assertTrue(document.fit_markdown)
        self.assertTrue(document.chunk_scores)
        self.assertTrue(document.selected_chunks)
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
        with (
            patch(
                "acquisition.fetch_pipeline.fetch_page",
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "acquisition.fetch_pipeline.render_document", return_value=fallback_doc
            ),
        ):
            document = fetch_document("https://example.com", use_render_fallback=True)
        self.assertTrue(document.used_render_fallback)
        self.assertEqual(document.title, "Rendered")

    def test_render_document_uses_local_playwright_renderer(self):
        with patch(
            "acquisition.render_pipeline._render_with_playwright",
            return_value={
                "url": "https://example.com",
                "final_url": "https://example.com/docs",
                "title": "Rendered Title",
                "raw_html": "<html><head><title>Rendered Title</title></head><body><p>Rendered body</p></body></html>",
            },
        ):
            document = render_document("https://example.com")
        self.assertTrue(document.used_render_fallback)
        self.assertEqual(document.final_url, "https://example.com/docs")
        self.assertIn("Rendered body", document.text)

    def test_fetch_document_can_use_optional_crawl4ai_adapter(self):
        fake_result = type(
            "FakeCrawlResult",
            (),
            {
                "markdown": "planner executor synthesizer",
                "fit_markdown": "planner executor",
                "html": "<html></html>",
                "url": "https://example.com/docs",
                "title": "Crawl4AI",
                "text": "planner executor synthesizer",
                "references": [{"url": "https://example.com/ref", "text": "Ref"}],
            },
        )()

        class FakeCrawler:
            def run(self, url, timeout=10):
                return fake_result

        fake_module = type(
            "FakeModule",
            (),
            {"WebCrawler": FakeCrawler},
        )()
        with (
            patch(
                "acquisition.crawl4ai_adapter.importlib.util.find_spec",
                return_value=object(),
            ),
            patch.dict(sys.modules, {"crawl4ai": fake_module}),
        ):
            document = fetch_with_crawl4ai("https://example.com")
        self.assertTrue(document.document_id)
        self.assertEqual(document.fetch_method, "crawl4ai")
        self.assertEqual(document.metadata["pipeline"], "crawl4ai")
        self.assertEqual(document.title, "Crawl4AI")
        self.assertTrue(document.fit_markdown)
        self.assertTrue(document.chunk_scores)
        self.assertEqual(document.references[0]["url"], "https://example.com/ref")

    def test_query_aware_content_filter_keeps_relevant_middle_paragraph(self):
        text = "\n\n".join(
            [
                "Intro paragraph about agent systems.",
                "Unrelated filler about gardening and hobbies.",
                "Planner executor synthesizer pipeline with runtime skip and release gate.",
                "More unrelated filler content.",
                "Conclusion paragraph on evaluation harness design.",
            ]
        )
        selected = select_relevant_content(
            text, query="runtime skip release gate", max_chars=500
        )
        self.assertIn("Intro paragraph", selected)
        self.assertIn("runtime skip and release gate", selected)
        self.assertIn("Conclusion paragraph", selected)

    def test_query_aware_content_filter_selects_relevant_sentence_chunk(self):
        text = "\n\n".join(
            [
                "Intro paragraph about systems.",
                "This page has many details. The release gate blocks rollout on failed validation. Extra filler follows. Another sentence about unrelated UI polish.",
                "Final note about evaluation.",
            ]
        )
        selected = select_relevant_content(
            text, query="release gate validation", max_chars=350
        )
        self.assertIn("release gate blocks rollout", selected)

    def test_chunk_document_ranks_query_aligned_chunks(self):
        text = "\n\n".join(
            [
                "Intro paragraph about systems.",
                "This page has many details. The release gate blocks rollout on failed validation. Extra filler follows. Another sentence about unrelated UI polish.",
                "Final note about evaluation.",
            ]
        )
        chunks = chunk_document(text, query="release gate validation", limit=3)
        self.assertTrue(chunks)
        self.assertIn("release gate blocks rollout", chunks[1]["text"])

    def test_build_markdown_views_returns_chunk_scores(self):
        text = "\n\n".join(
            [
                "Intro paragraph about systems.",
                "This page has many details. The release gate blocks rollout on failed validation. Extra filler follows. Another sentence about unrelated UI polish.",
                "Final note about evaluation.",
            ]
        )
        views = build_markdown_views(
            text, query="release gate validation", max_chars=350
        )
        self.assertIn("clean_markdown", views)
        self.assertIn("fit_markdown", views)
        self.assertTrue(views["chunk_scores"])
        self.assertTrue(views["selected_chunks"])


if __name__ == "__main__":
    unittest.main()
