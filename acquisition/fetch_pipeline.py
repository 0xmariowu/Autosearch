"""Native fetch pipeline for acquired documents."""

from __future__ import annotations

import urllib.request

from .document_models import AcquiredDocument
from .markdown_cleaner import clean_markdown, fit_markdown
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
        payload = response.read().decode("utf-8", errors="replace")
    return {
        "url": str(url or "").strip(),
        "final_url": final_url,
        "content_type": content_type,
        "raw_html": payload,
    }


def fetch_document(
    url: str,
    *,
    timeout: int = 10,
    use_render_fallback: bool = False,
) -> AcquiredDocument:
    try:
        page = fetch_page(url, timeout=timeout)
        document = AcquiredDocument.from_html(
            page["url"],
            page["raw_html"],
            content_type=page["content_type"],
            final_url=page["final_url"],
        )
    except Exception:
        if not use_render_fallback:
            raise
        document = render_document(url, timeout=timeout)
    document.clean_markdown = clean_markdown(document.text)
    document.fit_markdown = fit_markdown(document.clean_markdown)
    document.references = extract_references(document.final_url, document.raw_html)
    return document
