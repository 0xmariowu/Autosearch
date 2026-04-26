from __future__ import annotations

import asyncio

import pytest

from autosearch.core.channel_runtime import ChannelRuntime
from autosearch.core.delegate import run_subtask
from autosearch.core.rate_limiter import RateLimiter
from autosearch.observability.channel_health import ChannelHealth


def _runtime() -> ChannelRuntime:
    return ChannelRuntime(
        registry=None,
        health=ChannelHealth(),
        limiter=RateLimiter(),
        channels=[],
    )


def test_channel_records_timeout() -> None:
    runtime = _runtime()

    runtime.record_timeout("slow")

    assert runtime.last_timeout_ts is not None
    assert runtime.channel_timeout_ts["slow"] == runtime.last_timeout_ts
    assert runtime.health.is_in_cooldown("slow") is True

    timeout_method = next(iter(runtime.health.snapshot()["slow"].values()))
    assert timeout_method["in_cooldown"] is True


@pytest.mark.asyncio
async def test_delegate_per_channel_timeout_records_runtime_cooldown() -> None:
    runtime = _runtime()

    async def _search(_channel_name: str) -> list[dict]:
        await asyncio.sleep(10)
        return []

    await run_subtask(
        "task",
        ["slow"],
        "query",
        channel_runtime=runtime,
        per_channel_timeout=0.01,
        _search_fn=_search,
    )

    assert runtime.channel_timeout_ts["slow"] == runtime.last_timeout_ts
    assert runtime.health.is_in_cooldown("slow") is True
