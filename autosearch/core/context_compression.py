"""Context compression — consolidate accumulated evidence into a compact research brief.

When a research session has many evidence items (from multiple run_channel calls),
the context window fills up. This module provides a way to compress evidence lists
into a concise brief that keeps the essential findings without the raw data.

Used by the consolidate_research MCP tool.
"""

from __future__ import annotations

from typing import Any

from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.models import Evidence

_processor = EvidenceProcessor()

MAX_BRIEF_EVIDENCE = 5  # Include at most 5 top items in brief
MAX_SNIPPET_CHARS = 120


def _evidence_from_dict(d: dict[str, Any]) -> Evidence | None:
    """Reconstruct Evidence from slim dict (best-effort)."""
    try:
        from datetime import UTC, datetime

        return Evidence(
            url=d.get("url", ""),
            title=d.get("title", ""),
            snippet=d.get("snippet"),
            content=d.get("content"),
            source_channel=d.get("source_channel", "unknown"),
            score=float(d.get("score") or 0.0),
            fetched_at=datetime.now(UTC),
        )
    except Exception:
        return None


def compress_evidence(
    evidence_list: list[dict[str, Any]],
    query: str,
    top_k: int = MAX_BRIEF_EVIDENCE,
) -> dict[str, Any]:
    """Compress a large evidence list into a compact research brief.

    Does NOT call an LLM — uses BM25 reranking + dedup to select the
    most relevant items, then formats them as a structured brief.

    Returns:
        {
          "query": str,
          "total_processed": int,
          "kept": int,
          "top_evidence": [slim dicts],
          "source_coverage": {"channel": count},
          "brief_text": "compact markdown summary",
        }
    """
    if not evidence_list:
        return {
            "query": query,
            "total_processed": 0,
            "kept": 0,
            "top_evidence": [],
            "source_coverage": {},
            "brief_text": "No evidence to summarize.",
        }

    # Reconstruct Evidence objects
    evs = [e for d in evidence_list if (e := _evidence_from_dict(d)) and e.url]

    # Quality pipeline
    evs = _processor.dedup_urls(evs)
    evs = _processor.dedup_simhash(evs)
    evs = _processor.rerank_bm25(evs, query, top_k=top_k)

    # Source coverage (before top-k)
    all_evs_for_coverage = [e for d in evidence_list if (e := _evidence_from_dict(d)) and e.url]
    source_coverage: dict[str, int] = {}
    for ev in all_evs_for_coverage:
        ch = ev.source_channel.split(":")[0] if ev.source_channel else "unknown"
        source_coverage[ch] = source_coverage.get(ch, 0) + 1

    # Build brief text
    lines = [f"**Research Brief** — `{query}`\n"]
    lines.append(f"Processed {len(evidence_list)} items → kept top {len(evs)} by relevance.\n")
    lines.append(f"Sources: {', '.join(f'{c}({n})' for c, n in sorted(source_coverage.items()))}\n")
    lines.append("\n**Top findings:**\n")

    for i, ev in enumerate(evs, 1):
        snippet = (ev.snippet or ev.content or "")[:MAX_SNIPPET_CHARS]
        if snippet and len(snippet) == MAX_SNIPPET_CHARS:
            snippet += "…"
        lines.append(f"{i}. [{ev.title}]({ev.url})  \n   {snippet}")

    return {
        "query": query,
        "total_processed": len(evidence_list),
        "kept": len(evs),
        "top_evidence": [ev.to_slim_dict() for ev in evs],
        "source_coverage": source_coverage,
        "brief_text": "\n".join(lines),
    }
