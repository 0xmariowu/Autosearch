"""Chunking helpers inspired by Crawl4AI-style extraction stages."""

from __future__ import annotations

from typing import Any

from .content_filter import rank_relevant_chunks


def chunk_document(
    text: str, *, query: str = "", limit: int = 4
) -> list[dict[str, Any]]:
    return rank_relevant_chunks(text, query=query, limit=limit)
