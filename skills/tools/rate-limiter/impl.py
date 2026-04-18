# Self-written, plan autosearch-0418-channels-and-skills.md § F002a
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

try:
    from autosearch.channels.base import RateLimited
except ImportError:

    class RateLimited(Exception):
        """Raised when a requested rate-limited acquire would wait too long."""


@dataclass
class _Bucket:
    capacity: int
    refill_rate: float
    tokens: float
    updated_at: float


class RateLimiter:
    """Per-(channel, method) token bucket.

    Usage:
        limiter = RateLimiter()
        async with limiter.acquire("zhihu", "api_search", per_min=30):
            ...

    Raises RateLimited when bucket exhausted and wait would exceed `max_wait_seconds`.
    """

    def __init__(
        self,
        max_wait_seconds: float = 30.0,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.max_wait_seconds = max_wait_seconds
        self._now = now
        self._sleep = sleep
        self._buckets: dict[tuple[str, str, str], _Bucket] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    @asynccontextmanager
    async def acquire(
        self,
        channel: str,
        method: str,
        per_min: int | None = None,
        per_hour: int | None = None,
    ) -> AsyncIterator[None]:
        limits = self._build_limits(per_min=per_min, per_hour=per_hour)
        if not limits:
            yield
            return

        lock = self._locks.setdefault((channel, method), asyncio.Lock())

        while True:
            async with lock:
                current = self._now()
                buckets = [
                    self._get_bucket(
                        channel=channel,
                        method=method,
                        scope=scope,
                        capacity=capacity,
                        refill_rate=refill_rate,
                        current=current,
                    )
                    for scope, capacity, refill_rate in limits
                ]
                wait_seconds = max(self._wait_for_token(bucket) for bucket in buckets)
                if wait_seconds == 0:
                    for bucket in buckets:
                        bucket.tokens -= 1
                    break

            if wait_seconds > self.max_wait_seconds:
                raise RateLimited(
                    f"Rate limit exhausted for {channel}.{method}; wait={wait_seconds:.3f}s"
                )
            await self._sleep(wait_seconds)

        try:
            yield
        finally:
            return

    def _build_limits(
        self,
        *,
        per_min: int | None,
        per_hour: int | None,
    ) -> list[tuple[str, int, float]]:
        limits: list[tuple[str, int, float]] = []
        if per_min is not None:
            if per_min <= 0:
                raise ValueError("per_min must be positive")
            limits.append(("minute", per_min, per_min / 60.0))
        if per_hour is not None:
            if per_hour <= 0:
                raise ValueError("per_hour must be positive")
            limits.append(("hour", per_hour, per_hour / 3600.0))
        return limits

    def _get_bucket(
        self,
        *,
        channel: str,
        method: str,
        scope: str,
        capacity: int,
        refill_rate: float,
        current: float,
    ) -> _Bucket:
        key = (channel, method, scope)
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(
                capacity=capacity,
                refill_rate=refill_rate,
                tokens=float(capacity),
                updated_at=current,
            )
            self._buckets[key] = bucket
            return bucket

        self._refill(bucket, current)
        bucket.capacity = capacity
        bucket.refill_rate = refill_rate
        bucket.tokens = min(bucket.tokens, float(capacity))
        return bucket

    def _refill(self, bucket: _Bucket, current: float) -> None:
        elapsed = max(0.0, current - bucket.updated_at)
        if elapsed == 0:
            return
        bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_rate)
        bucket.updated_at = current

    def _wait_for_token(self, bucket: _Bucket) -> float:
        if bucket.tokens >= 1:
            return 0.0
        return (1 - bucket.tokens) / bucket.refill_rate
