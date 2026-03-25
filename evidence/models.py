"""Evidence record model helpers."""

from __future__ import annotations

from typing import Any

from .classify import clean_text, evidence_content_type, evidence_domain


def build_evidence_record(
    *,
    title: str,
    url: str,
    body: str,
    source: str,
    query: str,
    clean_markdown: str = "",
    fit_markdown: str = "",
    references: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    clean_title = clean_text(title, limit=240)
    snippet = clean_text(body, limit=500)
    domain = evidence_domain(url)
    content_type = evidence_content_type(source, url)
    canonical_parts = [clean_title, snippet]
    if fit_markdown:
        canonical_parts.append(clean_text(fit_markdown, limit=1200))
    canonical_text = "\n\n".join(part for part in canonical_parts if part).strip()
    return {
        "record_type": "evidence",
        "title": clean_title,
        "url": str(url or "").strip(),
        "body": snippet,
        "snippet": snippet,
        "source": str(source or "").strip(),
        "provider": str(source or "").strip(),
        "query": str(query or "").strip(),
        "domain": domain,
        "content_type": content_type,
        "canonical_text": canonical_text,
        "clean_markdown": str(clean_markdown or ""),
        "fit_markdown": str(fit_markdown or ""),
        "references": list(references or []),
    }
