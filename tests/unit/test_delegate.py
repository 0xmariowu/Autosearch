from __future__ import annotations

import asyncio
import inspect
from typing import cast

import pytest

from autosearch.channels.base import RateLimited
from autosearch.core.channel_runtime import ChannelRuntime
from autosearch.core.delegate import run_subtask

_UNUSED_RUNTIME = cast(ChannelRuntime, object())


def test_run_subtask_requires_channel_runtime() -> None:
    signature = inspect.signature(run_subtask)
    channel_runtime = signature.parameters.get("channel_runtime")

    assert channel_runtime is not None
    assert channel_runtime.default is inspect.Parameter.empty


@pytest.mark.asyncio
async def test_run_subtask_propagates_runtime_rate_limit() -> None:
    """A RateLimited from the search path surfaces as a failed_channel
    with rate_limited status — the runtime contract callers depend on."""

    async def _search(name: str) -> list[dict]:
        raise RateLimited(f"rate-limited: {name}.search retry_after=10s")

    result = await run_subtask(
        "task",
        ["alpha"],
        "query",
        channel_runtime=_UNUSED_RUNTIME,
        _search_fn=_search,
    )

    assert result.failed_channels == ["alpha"]
    assert result.failed_channel_details[0]["status"] == "rate_limited"


@pytest.mark.asyncio
async def test_run_subtask_dedupes_repeated_channels() -> None:
    """The same channel name passed twice must only run once."""
    call_counts: dict[str, int] = {}

    async def _search(name: str) -> list[dict]:
        call_counts[name] = call_counts.get(name, 0) + 1
        return [{"channel": name}]

    result = await run_subtask(
        "task",
        ["alpha", "beta", "alpha"],
        "query",
        channel_runtime=_UNUSED_RUNTIME,
        _search_fn=_search,
    )

    assert call_counts == {"alpha": 1, "beta": 1}
    assert set(result.evidence_by_channel.keys()) == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_run_subtask_respects_concurrency_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUTOSEARCH_DELEGATE_CONCURRENCY caps in-flight channel calls."""
    monkeypatch.setenv("AUTOSEARCH_DELEGATE_CONCURRENCY", "2")

    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def _search(name: str) -> list[dict]:
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        async with lock:
            in_flight -= 1
        return [{"channel": name}]

    channels = [f"ch{i}" for i in range(8)]

    await run_subtask(
        "task",
        channels,
        "query",
        channel_runtime=_UNUSED_RUNTIME,
        _search_fn=_search,
    )

    assert max_in_flight <= 2, f"expected cap 2, observed {max_in_flight}"
