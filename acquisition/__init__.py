"""Acquisition package.

Stable local boundary for:
- fetching documents
- optional rendered fallback
- markdown cleaning / trimming
- reference extraction
- evidence enrichment
"""

from .document_models import AcquiredDocument
from .fetch_pipeline import fetch_document, fetch_page
from .markdown_cleaner import clean_markdown, fit_markdown
from .reference_extractor import extract_references
from .render_pipeline import render_document

__all__ = [
    "AcquiredDocument",
    "clean_markdown",
    "enrich_evidence_record",
    "extract_references",
    "extract_visible_text",
    "fetch_document",
    "fetch_page",
    "fit_markdown",
    "render_document",
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
) -> dict:
    enriched = dict(record)
    url = str(record.get("url") or "").strip()
    if not url:
        enriched["acquired"] = False
        enriched["acquisition_error"] = "missing url"
        return enriched
    try:
        page = fetch_page(url, timeout=timeout)
        if "raw_html" in page:
            document = AcquiredDocument.from_html(
                page["url"],
                page["raw_html"],
                content_type=page.get("content_type", ""),
                final_url=page.get("final_url", page["url"]),
            )
            document.clean_markdown = clean_markdown(document.text)
            document.fit_markdown = fit_markdown(document.clean_markdown)
            document.references = extract_references(document.final_url, document.raw_html)
        else:
            document = AcquiredDocument(
                url=url,
                final_url=str(page.get("final_url") or url),
                content_type=str(page.get("content_type") or ""),
                title=str(page.get("title") or ""),
                text=str(page.get("text") or ""),
                raw_html=str(page.get("raw_html") or ""),
            )
            document.clean_markdown = clean_markdown(document.text)
            document.fit_markdown = fit_markdown(document.clean_markdown)
            document.references = list(page.get("references") or [])
    except Exception as exc:
        if not use_render_fallback:
            enriched["acquired"] = False
            enriched["acquisition_error"] = str(exc)
            return enriched
        try:
            document = render_document(url, timeout=timeout)
            document.clean_markdown = clean_markdown(document.text)
            document.fit_markdown = fit_markdown(document.clean_markdown)
            document.references = extract_references(document.final_url, document.raw_html)
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
    enriched["references"] = list(document.references)
    return enriched
