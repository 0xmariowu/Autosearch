"""In-process rate limiter for channel methods.

Plan §P0-6: every channel `SKILL.md` declares `rate_limit: {per_min, per_hour}`,
but the runtime never enforced it. Free upstreams could be hammered; paid
providers like TikHub burned budget unexpectedly. This module enforces those
declared limits with a sliding-window counter per `(channel, method)`.

Sliding-window choice: simple deque of timestamps, dropping anything older
than the longest window we care about. Cheaper than token-bucket because we
don't need fractional refills, and easy to reason about under bursty load.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Per-(channel, method) sliding-window limiter. Thread-safe.

    `acquire(channel, method, per_min, per_hour)` returns `(allowed, retry_after_seconds)`.
    `retry_after_seconds` is 0 when allowed, otherwise the number of seconds until
    the oldest in-window event ages out (whichever window is currently exceeded).
    """

    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        self._now = now
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def acquire(
        self,
        channel: str,
        method: str,
        *,
        per_min: int | None = None,
        per_hour: int | None = None,
    ) -> tuple[bool, float]:
        """Try to consume a slot. Returns (allowed, retry_after_seconds)."""
        # No declared limit → never rate-limited.
        if not per_min and not per_hour:
            return True, 0.0

        key = (channel, method)
        now = self._now()
        with self._lock:
            window = self._events[key]
            # Trim anything older than the largest window we care about.
            cutoff = now - 3600.0 if per_hour else now - 60.0
            while window and window[0] < cutoff:
                window.popleft()

            # Hour check.
            if per_hour:
                hour_count = sum(1 for ts in window if ts >= now - 3600.0)
                if hour_count >= per_hour:
                    oldest = next((ts for ts in window if ts >= now - 3600.0), now)
                    retry = max(0.0, (oldest + 3600.0) - now)
                    return False, retry

            # Minute check.
            if per_min:
                minute_count = sum(1 for ts in window if ts >= now - 60.0)
                if minute_count >= per_min:
                    oldest = next((ts for ts in window if ts >= now - 60.0), now)
                    retry = max(0.0, (oldest + 60.0) - now)
                    return False, retry

            # Allowed — record the event.
            window.append(now)
            return True, 0.0

    def snapshot(self) -> dict[tuple[str, str], int]:
        """Return current in-window event counts per (channel, method)."""
        now = self._now()
        with self._lock:
            return {
                key: sum(1 for ts in events if ts >= now - 3600.0)
                for key, events in self._events.items()
            }
