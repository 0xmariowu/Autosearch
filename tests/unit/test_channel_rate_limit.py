"""Plan §P0-6: declared `rate_limit: {per_min, per_hour}` in SKILL.md must be
enforced at runtime, not just metadata.

Pre-fix: declarations were parsed and stored on `MethodSpec.rate_limit` but
never consulted before invoking the method callable. Free upstreams could be
hammered, paid TikHub burned budget. Now `_CompiledChannel.search` consults
the runtime `RateLimiter` per (channel, method) and raises `RateLimited` when
the window is exhausted; `run_channel` reports `status="rate_limited"`."""

from __future__ import annotations

from autosearch.core.rate_limiter import RateLimiter


def test_rate_limiter_passthrough_when_no_limit():
    rl = RateLimiter()
    for _ in range(5):
        allowed, retry = rl.acquire("c", "m")
        assert allowed is True
        assert retry == 0.0


def test_rate_limiter_per_min_blocks_after_quota():
    """Sliding-window per-minute cap. Six calls with per_min=3 → first 3 allow,
    rest deny with positive retry_after."""
    clock = {"t": 0.0}
    rl = RateLimiter(now=lambda: clock["t"])
    results = []
    for _ in range(6):
        results.append(rl.acquire("yt", "search", per_min=3))
        clock["t"] += 1.0  # 1 second between calls

    allowed = [r[0] for r in results]
    assert allowed[:3] == [True, True, True]
    assert allowed[3:] == [False, False, False]
    # retry_after should be the seconds until the oldest event ages out
    for blocked, retry in results[3:]:
        assert retry > 0


def test_rate_limiter_per_hour_blocks_independently():
    clock = {"t": 0.0}
    rl = RateLimiter(now=lambda: clock["t"])
    # per_min=10 (very loose), per_hour=2 (tight) — hour limit must bite first
    a1, _ = rl.acquire("yt", "s", per_min=10, per_hour=2)
    a2, _ = rl.acquire("yt", "s", per_min=10, per_hour=2)
    a3, retry = rl.acquire("yt", "s", per_min=10, per_hour=2)
    assert a1 is True and a2 is True
    assert a3 is False
    # Should be near 3600 since events were just recorded
    assert 3500 < retry <= 3600


def test_rate_limiter_window_slides():
    clock = {"t": 0.0}
    rl = RateLimiter(now=lambda: clock["t"])
    # Fill quota
    for _ in range(3):
        assert rl.acquire("c", "m", per_min=3)[0] is True
    # Immediately denied
    assert rl.acquire("c", "m", per_min=3)[0] is False
    # Advance past the window
    clock["t"] += 61.0
    # Now allowed again
    assert rl.acquire("c", "m", per_min=3)[0] is True


def test_rate_limiter_keyed_per_channel_method():
    """Limits don't leak across different (channel, method) pairs."""
    rl = RateLimiter()
    for _ in range(3):
        assert rl.acquire("a", "m", per_min=3)[0] is True
    # Different channel, same method id — fresh quota
    assert rl.acquire("b", "m", per_min=3)[0] is True
    # Different method id, same channel — also fresh
    assert rl.acquire("a", "n", per_min=3)[0] is True


def test_rate_limited_method_in_compiled_channel_raises_RateLimited(tmp_path):
    """End-to-end: compile a fixture channel with per_min=2, call .search()
    three times — the third must raise RateLimited (so run_channel can map
    it to status='rate_limited')."""
    import asyncio
    from textwrap import dedent

    from autosearch.channels.base import (
        ChannelRegistry,
        Environment,
        RateLimited,
    )
    from autosearch.core.models import SubQuery
    from autosearch.core.rate_limiter import RateLimiter

    root = tmp_path / "channels"
    skill = root / "limited_chan"
    (skill / "methods").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        dedent(
            """
            ---
            name: limited_chan
            description: "rate limit fixture"
            version: 1
            languages: [en]
            methods:
              - id: api
                impl: methods/api.py
                requires: []
                rate_limit: {per_min: 2}
            fallback_chain: [api]
            ---
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (skill / "methods" / "api.py").write_text(
        dedent(
            """
            from datetime import UTC, datetime
            from autosearch.core.models import Evidence, SubQuery


            async def search(q: SubQuery) -> list[Evidence]:
                return [Evidence(
                    url="https://example.com/x",
                    title="x",
                    snippet="",
                    source_channel="limited_chan:api",
                    fetched_at=datetime.now(UTC),
                )]
            """
        ).lstrip(),
        encoding="utf-8",
    )

    registry = ChannelRegistry.compile_from_skills(root, Environment())
    registry.attach_limiter(RateLimiter())
    chan = registry.get("limited_chan")
    q = SubQuery(text="test", rationale="rate-limit test")

    # First two calls should succeed
    asyncio.run(chan.search(q))
    asyncio.run(chan.search(q))

    # Third call should hit per_min=2 cap
    import pytest

    with pytest.raises(RateLimited, match="rate_limited"):
        asyncio.run(chan.search(q))
