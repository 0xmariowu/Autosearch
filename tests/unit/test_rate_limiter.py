# Self-written, plan autosearch-0418-channels-and-skills.md § F002a
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_module(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _rate_limiter_module() -> ModuleType:
    root = Path(__file__).resolve().parents[2]
    return _load_module(
        "test_rate_limiter_impl",
        root / "skills" / "tools" / "rate-limiter" / "impl.py",
    )


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.value = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


@pytest.mark.asyncio
async def test_acquire_within_budget_does_not_block() -> None:
    module = _rate_limiter_module()
    clock = _FakeClock()
    limiter = module.RateLimiter(now=clock.now, sleep=clock.sleep)

    for _ in range(5):
        async with limiter.acquire("zhihu", "api_search", per_min=60):
            pass

    assert clock.sleeps == []
    assert clock.value == 0.0


@pytest.mark.asyncio
async def test_acquire_blocks_when_exhausted() -> None:
    module = _rate_limiter_module()
    clock = _FakeClock()
    limiter = module.RateLimiter(now=clock.now, sleep=clock.sleep)

    async with limiter.acquire("zhihu", "api_search", per_min=2):
        pass
    async with limiter.acquire("zhihu", "api_search", per_min=2):
        pass
    async with limiter.acquire("zhihu", "api_search", per_min=2):
        pass

    assert len(clock.sleeps) == 1
    assert clock.sleeps[0] == pytest.approx(30.0)
    assert clock.value == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_acquire_raises_rate_limited_when_max_wait_exceeded() -> None:
    module = _rate_limiter_module()
    clock = _FakeClock()
    limiter = module.RateLimiter(max_wait_seconds=0.001, now=clock.now, sleep=clock.sleep)

    async with limiter.acquire("zhihu", "api_search", per_min=1):
        pass

    with pytest.raises(module.RateLimited):
        async with limiter.acquire("zhihu", "api_search", per_min=1):
            pass

    assert clock.sleeps == []


@pytest.mark.asyncio
async def test_per_hour_limit_tighter_than_per_min() -> None:
    module = _rate_limiter_module()
    clock = _FakeClock()
    limiter = module.RateLimiter(max_wait_seconds=2000.0, now=clock.now, sleep=clock.sleep)

    async with limiter.acquire("zhihu", "api_search", per_min=60, per_hour=2):
        pass
    async with limiter.acquire("zhihu", "api_search", per_min=60, per_hour=2):
        pass
    async with limiter.acquire("zhihu", "api_search", per_min=60, per_hour=2):
        pass

    assert len(clock.sleeps) == 1
    assert clock.sleeps[0] == pytest.approx(1800.0)


@pytest.mark.asyncio
async def test_independent_buckets_per_channel_method() -> None:
    module = _rate_limiter_module()
    clock = _FakeClock()
    limiter = module.RateLimiter(now=clock.now, sleep=clock.sleep)

    async with limiter.acquire("a", "m1", per_min=1):
        pass
    async with limiter.acquire("b", "m1", per_min=1):
        pass
    async with limiter.acquire("a", "m2", per_min=1):
        pass

    assert clock.sleeps == []


@pytest.mark.asyncio
async def test_refill_over_time_allows_new_acquire() -> None:
    module = _rate_limiter_module()
    clock = _FakeClock()
    limiter = module.RateLimiter(now=clock.now, sleep=clock.sleep)

    async with limiter.acquire("zhihu", "api_search", per_min=2):
        pass
    async with limiter.acquire("zhihu", "api_search", per_min=2):
        pass

    clock.value += 30.0

    async with limiter.acquire("zhihu", "api_search", per_min=2):
        pass

    assert clock.sleeps == []
    assert clock.value == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_acquire_without_limits_is_noop() -> None:
    module = _rate_limiter_module()
    clock = _FakeClock()
    limiter = module.RateLimiter(now=clock.now, sleep=clock.sleep)

    async with limiter.acquire("zhihu", "api_search"):
        pass

    assert clock.sleeps == []
    assert clock.value == 0.0
