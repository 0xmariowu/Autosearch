# Self-written, plan autosearch-0418-channels-and-skills.md § F001
from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(slots=True)
class _MethodHealthState:
    success_count: int = 0
    fail_count: int = 0
    cooldown_until: float | None = None
    history: deque[tuple[float, bool]] = field(default_factory=deque)
    consecutive_failures: deque[float] = field(default_factory=deque)
    last_error: str | None = None
    last_latency_ms: float | None = None


class ChannelHealth:
    """Per-(channel, method) success rate + cooldown tracker.

    Failure threshold: 3 consecutive failures within 5 min → cooldown for 5 min.
    Success resets the failure streak.
    """

    _failure_window_seconds = 300

    def __init__(
        self,
        fail_threshold: int = 3,
        cooldown_seconds: int = 300,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fail_threshold = fail_threshold
        self._cooldown_seconds = cooldown_seconds
        self._now = now
        self._states: dict[str, dict[str, _MethodHealthState]] = defaultdict(dict)

    def record(
        self,
        channel: str,
        method: str,
        success: bool,
        latency_ms: float,
        error: str | None = None,
    ) -> None:
        state = self._states[channel].setdefault(method, _MethodHealthState())
        now = self._now()

        state.history.append((now, success))
        state.last_latency_ms = latency_ms
        state.last_error = error

        if success:
            state.success_count += 1
            state.consecutive_failures.clear()
            return

        state.fail_count += 1
        state.consecutive_failures.append(now)
        while (
            state.consecutive_failures
            and now - state.consecutive_failures[0] > self._failure_window_seconds
        ):
            state.consecutive_failures.popleft()

        if len(state.consecutive_failures) >= self._fail_threshold:
            state.cooldown_until = now + self._cooldown_seconds
            state.consecutive_failures.clear()

    def is_in_cooldown(self, channel: str, method: str | None = None) -> bool:
        now = self._now()
        if method is not None:
            return self._method_in_cooldown(channel, method, now)

        return any(
            self._method_in_cooldown(channel, method_name, now)
            for method_name in self._states.get(channel, {})
        )

    def success_rate(self, channel: str, method: str, window_seconds: int = 3600) -> float:
        state = self._states.get(channel, {}).get(method)
        if state is None:
            return 0.0

        cutoff = self._now() - window_seconds
        window = [success for ts, success in state.history if ts >= cutoff]
        if not window:
            return 0.0

        return sum(1 for success in window if success) / len(window)

    def snapshot(self) -> dict[str, dict]:
        now = self._now()
        snapshot: dict[str, dict] = {}
        for channel, methods in self._states.items():
            snapshot[channel] = {}
            for method, state in methods.items():
                cooldown_until = state.cooldown_until
                in_cooldown = cooldown_until is not None and cooldown_until > now
                snapshot[channel][method] = {
                    "success_count": state.success_count,
                    "fail_count": state.fail_count,
                    "in_cooldown": in_cooldown,
                    "cooldown_until": cooldown_until if in_cooldown else None,
                }

        return snapshot

    def _method_in_cooldown(self, channel: str, method: str, now: float) -> bool:
        state = self._states.get(channel, {}).get(method)
        if state is None or state.cooldown_until is None:
            return False

        return state.cooldown_until > now
