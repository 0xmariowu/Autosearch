from __future__ import annotations

import asyncio
from textwrap import dedent

import pytest

from autosearch.channels.base import ChannelRegistry, Environment, MethodUnavailable
from autosearch.core.channel_runtime import ChannelRuntime
from autosearch.core.delegate import run_subtask
from autosearch.core.models import SubQuery
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

    runtime.record_timeout("slow", latency_ms=123.0)

    assert runtime.last_timeout_ts is not None
    assert runtime.channel_timeout_ts["slow"] == runtime.last_timeout_ts
    assert runtime.health.is_in_cooldown("slow") is True
    assert runtime.health.is_in_cooldown("slow", "search") is True
    assert getattr(runtime.health, "_states")["slow"]["search"].last_latency_ms == 123.0

    timeout_method = next(iter(runtime.health.snapshot()["slow"].values()))
    assert timeout_method["in_cooldown"] is True


@pytest.mark.asyncio
async def test_recorded_timeout_cools_down_next_compiled_channel_search(tmp_path) -> None:
    root = tmp_path / "channels"
    skill = root / "slow"
    (skill / "methods").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        dedent(
            """
            ---
            name: slow
            description: "timeout fixture"
            version: 1
            languages: [en]
            methods:
              - id: api
                impl: methods/api.py
                requires: []
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
                    source_channel="slow:api",
                    fetched_at=datetime.now(UTC),
                )]
            """
        ).lstrip(),
        encoding="utf-8",
    )

    registry = ChannelRegistry.compile_from_skills(root, Environment())
    health = ChannelHealth()
    registry.attach_health(health)
    channel = registry.get("slow")
    runtime = ChannelRuntime(
        registry=registry,
        health=health,
        limiter=RateLimiter(),
        channels=[channel],
    )

    runtime.record_timeout("slow", latency_ms=10.0)

    assert runtime.health.is_in_cooldown("slow", "api") is True
    assert "api" in runtime.health.snapshot()["slow"]
    with pytest.raises(MethodUnavailable, match="no available search methods"):
        await channel.search(SubQuery(text="query", rationale="query"))


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
    assert getattr(runtime.health, "_states")["slow"]["search"].last_latency_ms == 10.0
