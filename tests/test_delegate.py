"""Tests for autosearch.core.delegate."""

from __future__ import annotations


import pytest

from autosearch.core.delegate import run_subtask


async def _fake_search(name: str, results: list[dict], fail: bool = False):
    async def _fn(channel_name: str) -> list[dict]:
        if fail:
            raise RuntimeError(f"channel {channel_name} failed")
        return results

    return _fn


@pytest.mark.asyncio
async def test_parallel_returns_evidence_from_all_channels():
    async def _search(channel_name: str) -> list[dict]:
        return [{"url": f"https://{channel_name}.com/1", "title": "t"}]

    result = await run_subtask("task", ["ch_a", "ch_b"], "query", _search_fn=_search)
    assert "ch_a" in result.evidence_by_channel
    assert "ch_b" in result.evidence_by_channel
    assert result.failed_channels == []


@pytest.mark.asyncio
async def test_failed_channel_recorded_not_raised():
    async def _search(channel_name: str) -> list[dict]:
        if channel_name == "bad":
            raise RuntimeError("boom")
        return [{"url": "https://ok.com"}]

    result = await run_subtask("task", ["ok", "bad"], "query", _search_fn=_search)
    assert "ok" in result.evidence_by_channel
    assert "bad" in result.failed_channels
    assert "bad" not in result.evidence_by_channel


@pytest.mark.asyncio
async def test_max_per_channel_limits_evidence():
    async def _search(channel_name: str) -> list[dict]:
        return [{"url": f"https://x.com/{i}"} for i in range(20)]

    result = await run_subtask("task", ["ch"], "query", max_per_channel=3, _search_fn=_search)
    assert len(result.evidence_by_channel["ch"]) <= 3
