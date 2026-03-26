"""Markdown generation strategy for acquired documents."""

from __future__ import annotations

from typing import Any

from .chunking import chunk_document
from .markdown_cleaner import clean_markdown


def build_markdown_views(text: str, *, query: str = "", max_chars: int = 2400) -> dict[str, Any]:
    cleaned = clean_markdown(text)
    ranked_chunks = chunk_document(cleaned, query=query, limit=4)
    if not ranked_chunks:
        fit_markdown = cleaned[:max_chars].rsplit(" ", 1)[0].strip() or cleaned[:max_chars].strip()
        return {
            "clean_markdown": cleaned,
            "fit_markdown": fit_markdown,
            "chunk_scores": [],
            "selected_chunks": [],
        }
    selected_chunks = [str(item.get("text") or "").strip() for item in ranked_chunks if str(item.get("text") or "").strip()]
    fit_markdown = "\n\n".join(selected_chunks).strip()
    if not fit_markdown:
        fit_markdown = cleaned[:max_chars].rsplit(" ", 1)[0].strip() or cleaned[:max_chars].strip()
    if len(fit_markdown) > max_chars:
        fit_markdown = fit_markdown[:max_chars].rsplit(" ", 1)[0].strip() or fit_markdown[:max_chars].strip()
    return {
        "clean_markdown": cleaned,
        "fit_markdown": fit_markdown,
        "chunk_scores": [
            {
                "index": int(item.get("index", 0) or 0),
                "score": float(item.get("score", 0.0) or 0.0),
                "text": str(item.get("text") or "").strip(),
            }
            for item in ranked_chunks
        ],
        "selected_chunks": selected_chunks,
    }
