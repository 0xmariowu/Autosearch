"""Native fetch pipeline for acquired documents."""

from __future__ import annotations

import urllib.request

from .crawl4ai_adapter import crawl4ai_available, fetch_with_crawl4ai
from .document_models import AcquiredDocument
from .markdown_strategy import build_markdown_views
from .reference_extractor import extract_references
from .render_pipeline import render_document


def fetch_page(url: str, *, timeout: int = 10) -> dict:
    request = urllib.request.Request(
        str(url or "").strip(),
        headers={"User-Agent": "autosearch/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = str(response.headers.get("Content-Type") or "")
        final_url = str(getattr(response, "url", url) or url)
        status_code = int(getattr(response, "status", 200) or 200)
        payload = response.read().decode("utf-8", errors="replace")
    return {
        "url": str(url or "").strip(),
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "raw_html": payload,
    }


def fetch_document(
    url: str,
    *,
    query: str = "",
    timeout: int = 10,
    use_render_fallback: bool = False,
    use_crawl4ai: bool = False,
) -> AcquiredDocument:
    if use_crawl4ai and crawl4ai_available():
        return fetch_with_crawl4ai(url, timeout=timeout)
    try:
        page = fetch_page(url, timeout=timeout)
        document = AcquiredDocument.from_html(
            page["url"],
            page["raw_html"],
            content_type=page["content_type"],
            final_url=page["final_url"],
            status_code=int(page.get("status_code", 200) or 200),
            fetch_method="http_fetch",
            metadata={"pipeline": "native"},
        )
    except Exception:
        if not use_render_fallback:
            raise
        document = render_document(url, timeout=timeout)
    markdown_views = build_markdown_views(document.text, query=query)
    document.clean_markdown = str(markdown_views.get("clean_markdown") or "")
    document.fit_markdown = str(markdown_views.get("fit_markdown") or "")
    document.chunk_scores = list(markdown_views.get("chunk_scores") or [])
    document.selected_chunks = list(markdown_views.get("selected_chunks") or [])
    document.references = extract_references(document.final_url, document.raw_html)
    return document
