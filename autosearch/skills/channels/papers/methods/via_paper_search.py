# Self-written for task F203
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import structlog
from paper_search_mcp.academic_platforms.arxiv import ArxivSearcher
from paper_search_mcp.academic_platforms.biorxiv import BioRxivSearcher
from paper_search_mcp.academic_platforms.google_scholar import GoogleScholarSearcher
from paper_search_mcp.academic_platforms.medrxiv import MedRxivSearcher
from paper_search_mcp.academic_platforms.pubmed import PubMedSearcher
from paper_search_mcp.paper import Paper

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="papers")

SOURCES: dict[str, type] = {
    "arxiv": ArxivSearcher,
    "pubmed": PubMedSearcher,
    "biorxiv": BioRxivSearcher,
    "medrxiv": MedRxivSearcher,
    "google_scholar": GoogleScholarSearcher,
}


PER_SOURCE_TIMEOUT_SECONDS = 8.0


async def search(
    query: SubQuery,
    *,
    sources: dict[str, type] | None = None,
    max_results_per_source: int = 5,
    per_source_timeout_seconds: float = PER_SOURCE_TIMEOUT_SECONDS,
) -> list[Evidence]:
    active_sources = sources or SOURCES
    if os.getenv("AUTOSEARCH_LLM_MODE") == "dummy" and sources is None:
        return []
    fetched_at = datetime.now(UTC)
    source_items = list(active_sources.items())
    tasks = [
        asyncio.wait_for(
            asyncio.to_thread(_search_source, searcher_cls, query.text, max_results_per_source),
            timeout=per_source_timeout_seconds,
        )
        for _, searcher_cls in source_items
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    evidence_by_source: dict[str, list[Evidence]] = {}
    for (source_name, _), result in zip(source_items, results, strict=True):
        if isinstance(result, TimeoutError):
            LOGGER.warning(
                "papers_source_timeout",
                source=source_name,
                timeout_seconds=per_source_timeout_seconds,
            )
            evidence_by_source[source_name] = []
            continue
        if isinstance(result, Exception):
            LOGGER.warning("papers_source_failed", source=source_name, reason=str(result))
            evidence_by_source[source_name] = []
            continue

        evidence_by_source[source_name] = [
            evidence
            for paper in result
            if (
                evidence := _paper_to_evidence(
                    paper, source_name=source_name, fetched_at=fetched_at
                )
            )
            is not None
        ]

    return _dedupe_by_url(_interleave(evidence_by_source))


def _search_source(searcher_cls: type, query_text: str, max_results: int) -> list[Paper]:
    searcher = searcher_cls()
    return searcher.search(query_text, max_results)


def _paper_to_evidence(paper: Paper, *, source_name: str, fetched_at: datetime) -> Evidence | None:
    url = (paper.url or "").strip() or (paper.pdf_url or "").strip()
    if not url:
        return None

    abstract = (paper.abstract or "").strip()
    snippet = _truncate_on_word_boundary(abstract, max_length=300) if abstract else None
    content = abstract or snippet

    return Evidence(
        url=url,
        title=paper.title,
        snippet=snippet,
        content=content,
        source_channel=f"papers:{source_name}",
        fetched_at=fetched_at,
        score=0.0,
    )


def _truncate_on_word_boundary(text: str, *, max_length: int) -> str:
    if len(text) <= max_length:
        return text

    truncated = text[:max_length].rstrip()
    split_at = truncated.rfind(" ")
    if split_at > 0:
        truncated = truncated[:split_at].rstrip()

    return f"{truncated}…"


def _interleave(evidence_by_source: dict[str, list[Evidence]]) -> list[Evidence]:
    interleaved: list[Evidence] = []
    max_items = max((len(items) for items in evidence_by_source.values()), default=0)

    for index in range(max_items):
        for items in evidence_by_source.values():
            if index < len(items):
                interleaved.append(items[index])

    return interleaved


def _dedupe_by_url(evidences: list[Evidence]) -> list[Evidence]:
    seen_urls: set[str] = set()
    deduped: list[Evidence] = []

    for evidence in evidences:
        if evidence.url in seen_urls:
            continue
        seen_urls.add(evidence.url)
        deduped.append(evidence)

    return deduped
