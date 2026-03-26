"""Acquisition package.

Stable local boundary for:
- fetching documents
- optional rendered fallback
- markdown cleaning / trimming
- reference extraction
- evidence enrichment
"""

from .document_models import AcquiredDocument
from .crawl4ai_adapter import crawl4ai_available, fetch_with_crawl4ai
from .content_filter import select_relevant_content
from .chunking import chunk_document
from .fetch_pipeline import fetch_document, fetch_page
from .markdown_cleaner import clean_markdown, fit_markdown
from .markdown_strategy import build_markdown_views
from .reference_extractor import extract_references
from .render_pipeline import render_document

__all__ = [
    "AcquiredDocument",
    "clean_markdown",
    "chunk_document",
    "crawl4ai_available",
    "build_markdown_views",
    "enrich_evidence_record",
    "extract_references",
    "extract_visible_text",
    "fetch_document",
    "fetch_with_crawl4ai",
    "fetch_page",
    "fit_markdown",
    "render_document",
    "select_relevant_content",
]


def extract_visible_text(html: str) -> dict[str, str]:
    document = AcquiredDocument.from_html("about:blank", html, content_type="text/html")
    return {
        "title": document.title,
        "text": document.text,
    }


def enrich_evidence_record(
    record: dict,
    *,
    timeout: int = 10,
    use_render_fallback: bool = False,
    use_crawl4ai_adapter: bool = False,
    query: str = "",
) -> dict:
    enriched = dict(record)
    url = str(record.get("url") or "").strip()
    if not url:
        enriched["acquired"] = False
        enriched["acquisition_error"] = "missing url"
        return enriched
    try:
        if use_crawl4ai_adapter:
            document = fetch_with_crawl4ai(url, timeout=timeout)
        else:
            page = fetch_page(url, timeout=timeout)
            if "raw_html" in page:
                document = AcquiredDocument.from_html(
                    page["url"],
                    page["raw_html"],
                    content_type=page.get("content_type", ""),
                    final_url=page.get("final_url", page["url"]),
                )
                markdown_views = build_markdown_views(
                    document.text, query=query or str(record.get("query") or "")
                )
                document.clean_markdown = str(
                    markdown_views.get("clean_markdown") or ""
                )
                document.fit_markdown = str(markdown_views.get("fit_markdown") or "")
                document.chunk_scores = list(markdown_views.get("chunk_scores") or [])
                document.selected_chunks = list(
                    markdown_views.get("selected_chunks") or []
                )
                document.references = extract_references(
                    document.final_url, document.raw_html
                )
            else:
                document = AcquiredDocument(
                    url=url,
                    final_url=str(page.get("final_url") or url),
                    content_type=str(page.get("content_type") or ""),
                    title=str(page.get("title") or ""),
                    text=str(page.get("text") or ""),
                    raw_html=str(page.get("raw_html") or ""),
                )
                markdown_views = build_markdown_views(
                    document.text, query=query or str(record.get("query") or "")
                )
                document.clean_markdown = str(
                    markdown_views.get("clean_markdown") or ""
                )
                document.fit_markdown = str(markdown_views.get("fit_markdown") or "")
                document.chunk_scores = list(markdown_views.get("chunk_scores") or [])
                document.selected_chunks = list(
                    markdown_views.get("selected_chunks") or []
                )
                document.references = list(page.get("references") or [])
    except Exception as exc:
        if not use_render_fallback:
            enriched["acquired"] = False
            enriched["acquisition_error"] = str(exc)
            return enriched
        try:
            document = render_document(url, timeout=timeout)
            markdown_views = build_markdown_views(
                document.text, query=query or str(record.get("query") or "")
            )
            document.clean_markdown = str(markdown_views.get("clean_markdown") or "")
            document.fit_markdown = str(markdown_views.get("fit_markdown") or "")
            document.chunk_scores = list(markdown_views.get("chunk_scores") or [])
            document.selected_chunks = list(markdown_views.get("selected_chunks") or [])
            document.references = extract_references(
                document.final_url, document.raw_html
            )
        except Exception as render_exc:
            enriched["acquired"] = False
            enriched["acquisition_error"] = str(render_exc)
            return enriched
    enriched["acquired"] = True
    enriched["acquired_title"] = document.title
    enriched["acquired_text"] = document.text
    enriched["acquired_content_type"] = document.content_type
    enriched["clean_markdown"] = document.clean_markdown
    enriched["fit_markdown"] = document.fit_markdown
    enriched["chunk_scores"] = list(document.chunk_scores)
    enriched["selected_chunks"] = list(document.selected_chunks)
    enriched["references"] = list(document.references)
    return enriched
