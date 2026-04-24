"""Bug 3 (fix-plan): consolidate_research / compress_evidence used to read the
channel name from `source_channel`, but `run_channel` writes it under `source`
(via `Evidence.to_context_dict`). The mismatch made every consolidated item
look like it came from an "unknown" source — defeating cross-channel grouping.

This regression test pins both field names as accepted readers."""

from __future__ import annotations

from autosearch.core.context_compression import compress_evidence


def _evidence_from_run_channel(
    *, source_value: str, url: str = "https://arxiv.org/abs/2401.12345"
) -> dict:
    # Shape produced by run_channel → Evidence.to_context_dict():
    return {
        "url": url,
        "title": "BM25 ranking explained",
        "snippet": "BM25 weights ...",
        "source": source_value,  # <-- the key in dispute
        "score": 0.7,
    }


def test_compress_reads_source_key_from_run_channel_output() -> None:
    """run_channel emits `source`; compressor must NOT treat it as `unknown`."""
    items = [
        _evidence_from_run_channel(source_value="arxiv"),
        _evidence_from_run_channel(
            source_value="arxiv",
            url="https://arxiv.org/abs/2401.99999",
        ),
    ]
    brief = compress_evidence(items, query="bm25")
    coverage = brief["source_coverage"]
    assert "arxiv" in coverage, (
        f"compressor failed to recognize 'arxiv' from run_channel `source` key; coverage={coverage}"
    )
    assert "unknown" not in coverage, (
        f"compressor treated run_channel output as unknown source: {coverage}"
    )


def test_compress_still_reads_explicit_source_channel_key() -> None:
    """Backward-compat: callers that already write `source_channel` keep working."""
    items = [
        {
            "url": "https://github.com/foo/bar",
            "title": "x",
            "snippet": "y",
            "source_channel": "github",
            "score": 0.5,
        }
    ]
    brief = compress_evidence(items, query="x")
    assert "github" in brief["source_coverage"]
    assert "unknown" not in brief["source_coverage"]
