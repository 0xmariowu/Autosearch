# Self-written, plan v2.3 § 13.5
from datetime import datetime

from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.models import Evidence

NOW = datetime(2026, 4, 17, 12, 0, 0)


def make_evidence(
    url: str,
    title: str,
    *,
    snippet: str | None = None,
    content: str | None = None,
    source_channel: str = "web",
) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=content,
        source_channel=source_channel,
        fetched_at=NOW,
    )


def test_dedup_urls_keeps_first_duplicate_url() -> None:
    processor = EvidenceProcessor()
    first = make_evidence("https://example.com/shared", "First title")
    duplicate = make_evidence("https://example.com/shared", "Second title")
    unique = make_evidence("https://example.com/unique", "Unique title")

    deduped = processor.dedup_urls([first, duplicate, unique])

    assert deduped == [first, unique]


def test_dedup_simhash_drops_near_duplicate_content() -> None:
    processor = EvidenceProcessor()
    original = make_evidence(
        "https://example.com/one",
        "Pricing update",
        content="Policy update pricing tiers for enterprise customers in 2026",
    )
    near_duplicate = make_evidence(
        "https://example.com/two",
        "Pricing update",
        content="Policy update pricing tiers for enterprise customers in 2025",
    )
    distinct = make_evidence(
        "https://example.com/three",
        "Security overview",
        content="Security controls and incident response guidance for hosted search",
    )

    deduped = processor.dedup_simhash([original, near_duplicate, distinct], threshold=3)

    assert deduped == [original, distinct]


def test_rerank_bm25_orders_results_sets_scores_and_applies_top_k() -> None:
    processor = EvidenceProcessor()
    evidences = [
        make_evidence(
            "https://example.com/a",
            "BM25 guide",
            snippet="bm25 ranking algorithm explained",
            content="bm25 ranking search relevance score",
        ),
        make_evidence(
            "https://example.com/b",
            "Search index basics",
            snippet="index maintenance guide",
            content="sharding and indexing only",
        ),
        make_evidence(
            "https://example.com/c",
            "BM25 tuning",
            snippet="bm25 bm25 parameters",
            content="bm25 parameters and query terms",
        ),
    ]

    reranked = processor.rerank_bm25(evidences, "bm25 ranking", top_k=2)

    assert [evidence.url for evidence in reranked] == [
        "https://example.com/a",
        "https://example.com/c",
    ]
    assert len(reranked) == 2
    assert all(evidence.score is not None for evidence in reranked)
    assert reranked[0].score > reranked[1].score
