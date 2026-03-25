"""Normalize raw search/acquisition outputs into evidence records."""

from __future__ import annotations

from typing import Any

from .models import build_evidence_record


def normalize_result_record(result: Any, query: str) -> dict[str, Any]:
    return build_evidence_record(
        title=str(getattr(result, "title", "") or ""),
        url=str(getattr(result, "url", "") or ""),
        body=str(getattr(result, "body", "") or ""),
        source=str(getattr(result, "source", "") or ""),
        query=query,
    )


def normalize_acquired_document(
    document: Any,
    *,
    source: str,
    query: str,
) -> dict[str, Any]:
    return build_evidence_record(
        title=str(getattr(document, "title", "") or ""),
        url=str(getattr(document, "final_url", "") or getattr(document, "url", "") or ""),
        body=str(getattr(document, "text", "") or ""),
        source=source,
        query=query,
        clean_markdown=str(getattr(document, "clean_markdown", "") or ""),
        fit_markdown=str(getattr(document, "fit_markdown", "") or ""),
        references=list(getattr(document, "references", []) or []),
    )


def normalize_evidence_record(record: dict[str, Any]) -> dict[str, Any]:
    return build_evidence_record(
        title=str(record.get("title") or ""),
        url=str(record.get("url") or ""),
        body=str(record.get("body") or record.get("snippet") or record.get("canonical_text") or ""),
        source=str(record.get("source") or record.get("provider") or ""),
        query=str(record.get("query") or ""),
        clean_markdown=str(record.get("clean_markdown") or ""),
        fit_markdown=str(record.get("fit_markdown") or ""),
        references=list(record.get("references") or []),
    )
