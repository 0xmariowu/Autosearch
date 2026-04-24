"""Bug 4 (fix-plan): publish dates were dropped on the way to MCP context dicts,
so `recent_signal_fusion` couldn't rank by recency. This pins the end-to-end
flow: Evidence carries published_at → to_context_dict surfaces it under the
key recent_signal_fusion already looks for → fusion produces a non-trivial
recency ranking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from autosearch.core.models import Evidence
from autosearch.core.recent_signal_fusion import filter_recent


def _ev(url: str, age_days: int) -> Evidence:
    return Evidence(
        url=url,
        title=f"item from {age_days} days ago",
        snippet="bm25 ranking",
        source_channel="arxiv",
        fetched_at=datetime.now(UTC),
        published_at=datetime.now(UTC) - timedelta(days=age_days),
    )


def test_to_context_dict_emits_published_at_when_set() -> None:
    ev = _ev("https://arxiv.org/abs/x", age_days=3)
    ctx = ev.to_context_dict()
    assert "published_at" in ctx, (
        "Evidence with a known publish date must surface it in the slim "
        "context dict for recent_signal_fusion to consume"
    )


def test_to_context_dict_omits_published_at_when_unknown() -> None:
    ev = Evidence(
        url="https://example.com",
        title="t",
        source_channel="generic",
        fetched_at=datetime.now(UTC),
    )
    assert "published_at" not in ev.to_context_dict()


def test_recent_signal_fusion_uses_published_at_from_run_channel_dicts() -> None:
    """End-to-end: dicts shaped like run_channel output must rank by recency.

    Before this fix: every item lacked a date key in the slim context dict, so
    `filter_recent` excluded everything. After: the recent item survives the
    90-day window and the older one is dropped.
    """
    items = [
        _ev("https://arxiv.org/abs/old", age_days=400).to_context_dict(),
        _ev("https://arxiv.org/abs/new", age_days=2).to_context_dict(),
        _ev("https://arxiv.org/abs/mid", age_days=60).to_context_dict(),
    ]
    ranked = filter_recent(items, days=90)
    urls = [item.get("url") for item in ranked]
    assert "https://arxiv.org/abs/new" in urls, (
        f"recent_signal_fusion dropped the recent item; got {urls}"
    )
    assert "https://arxiv.org/abs/old" not in urls, (
        "filter_recent must exclude items older than the cutoff"
    )
    # Newest first ordering
    assert urls[0] == "https://arxiv.org/abs/new", f"expected newest first; got {urls}"
