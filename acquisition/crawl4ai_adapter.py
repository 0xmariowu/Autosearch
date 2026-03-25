"""Optional Crawl4AI adapter.

This module is an internal accelerator only. The native acquisition pipeline
must already work without it.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from .document_models import AcquiredDocument
from .markdown_cleaner import clean_markdown, fit_markdown


def crawl4ai_available() -> bool:
    return importlib.util.find_spec("crawl4ai") is not None


def fetch_with_crawl4ai(url: str, *, timeout: int = 10) -> AcquiredDocument:
    if not crawl4ai_available():
        raise RuntimeError("crawl4ai not installed")
    # Keep the adapter loose and resilient: use attribute probing instead of
    # binding our runtime to one Crawl4AI versioned API.
    module = __import__("crawl4ai")
    crawler_cls = getattr(module, "AsyncWebCrawler", None) or getattr(module, "WebCrawler", None)
    if crawler_cls is None:
        raise RuntimeError("crawl4ai crawler class not available")
    crawler = crawler_cls()
    runner = getattr(crawler, "run", None) or getattr(crawler, "crawl", None)
    if runner is None:
        raise RuntimeError("crawl4ai crawler missing run/crawl method")
    result = runner(str(url or "").strip(), timeout=timeout)
    markdown = str(getattr(result, "markdown", "") or getattr(result, "clean_markdown", "") or "")
    fit = str(getattr(result, "fit_markdown", "") or fit_markdown(markdown))
    html = str(getattr(result, "html", "") or getattr(result, "raw_html", "") or "")
    final_url = str(getattr(result, "url", "") or getattr(result, "final_url", "") or url)
    title = str(getattr(result, "title", "") or "").strip()
    text = str(getattr(result, "text", "") or markdown or fit or "").strip()
    document = AcquiredDocument(
        url=str(url or "").strip(),
        final_url=final_url,
        content_type="text/html",
        title=title,
        text=text,
        raw_html=html,
    )
    document.clean_markdown = markdown or clean_markdown(text)
    document.fit_markdown = fit or fit_markdown(document.clean_markdown)
    references = getattr(result, "references", None)
    if isinstance(references, list):
        document.references = list(references)
    return document
