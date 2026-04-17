# Self-written, plan v2.3 § 13.5
import time
from datetime import UTC, datetime

from autosearch.core.evidence import EvidenceProcessor
from autosearch.core.models import Evidence

NOW = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)


def _make_evidence(index: int) -> Evidence:
    query_mentions = " ".join(["query"] * ((index % 5) + 1))
    return Evidence(
        url=f"https://example.com/evidence-{index}",
        title=f"Synthetic query evidence {index}",
        snippet=f"query snippet {index} {query_mentions}",
        content=(
            f"Synthetic content {index} covers query relevance {query_mentions}. "
            f"It also includes varied terms bucket-{index % 10} and item-{index}."
        ),
        source_channel="web",
        fetched_at=NOW,
    )


def test_evidence_processor_handles_one_hundred_items_quickly() -> None:
    processor = EvidenceProcessor()
    evidences = [_make_evidence(index) for index in range(100)]

    started_at = time.perf_counter()
    url_deduped = processor.dedup_urls(evidences)
    simhash_deduped = processor.dedup_simhash(url_deduped, threshold=3)
    reranked = processor.rerank_bm25(evidences, "query", top_k=20)
    elapsed = time.perf_counter() - started_at

    assert len(url_deduped) == 100
    assert len(simhash_deduped) <= len(url_deduped)
    assert len(reranked) == 20
    assert all(evidence.score is not None for evidence in reranked)
    assert [evidence.score for evidence in reranked] == sorted(
        (evidence.score for evidence in reranked),
        reverse=True,
    )
    assert elapsed < 2.0
