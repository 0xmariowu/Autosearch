# Self-written, plan autosearch-0418-channels-and-skills.md § F001
from __future__ import annotations

import pytest

from autosearch.observability.channel_health import ChannelHealth


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_record_success_resets_streak() -> None:
    clock = FakeClock()
    health = ChannelHealth(now=clock)

    health.record("stub", "echo", success=False, latency_ms=2.0, error="timeout")
    clock.advance(10)
    health.record("stub", "echo", success=False, latency_ms=2.0, error="timeout")
    clock.advance(10)
    health.record("stub", "echo", success=True, latency_ms=1.0)
    clock.advance(10)
    health.record("stub", "echo", success=False, latency_ms=2.0, error="timeout")

    snapshot = health.snapshot()

    assert health.is_in_cooldown("stub", "echo") is False
    assert snapshot["stub"]["echo"]["success_count"] == 1
    assert snapshot["stub"]["echo"]["fail_count"] == 3


def test_three_fails_enters_cooldown() -> None:
    clock = FakeClock()
    health = ChannelHealth(now=clock)

    for _ in range(3):
        health.record("stub", "echo", success=False, latency_ms=3.0, error="rate_limit")
        clock.advance(1)

    snapshot = health.snapshot()

    assert health.is_in_cooldown("stub", "echo") is True
    assert snapshot["stub"]["echo"]["in_cooldown"] is True


def test_cooldown_expires_after_configured_seconds() -> None:
    clock = FakeClock()
    health = ChannelHealth(now=clock, cooldown_seconds=30)

    for _ in range(3):
        health.record("stub", "echo", success=False, latency_ms=4.0, error="transient")

    assert health.is_in_cooldown("stub", "echo") is True

    clock.advance(31)

    assert health.is_in_cooldown("stub", "echo") is False


def test_auth_and_permanent_failures_enter_long_cooldown() -> None:
    clock = FakeClock()
    health = ChannelHealth(now=clock, cooldown_seconds=30)

    health.record("stub", "auth", success=False, latency_ms=1.0, error="ChannelAuthError")
    health.record("stub", "permanent", success=False, latency_ms=1.0, error="PermanentError")

    clock.advance(31)

    assert health.is_in_cooldown("stub", "auth") is True
    assert health.is_in_cooldown("stub", "permanent") is True


def test_transient_and_rate_limited_failures_use_short_cooldown() -> None:
    clock = FakeClock()
    health = ChannelHealth(now=clock, cooldown_seconds=30)

    health.record("stub", "transient", success=False, latency_ms=1.0, error="TransientError")
    health.record("stub", "rate", success=False, latency_ms=1.0, error="RateLimited")

    assert health.is_in_cooldown("stub", "transient") is True
    assert health.is_in_cooldown("stub", "rate") is True

    clock.advance(31)

    assert health.is_in_cooldown("stub", "transient") is False
    assert health.is_in_cooldown("stub", "rate") is False


def test_is_in_cooldown_method_specific_vs_any() -> None:
    clock = FakeClock()
    health = ChannelHealth(now=clock)

    for _ in range(3):
        health.record("stub", "first", success=False, latency_ms=5.0, error="timeout")
    health.record("stub", "second", success=True, latency_ms=1.0)

    assert health.is_in_cooldown("stub", "first") is True
    assert health.is_in_cooldown("stub", "second") is False
    assert health.is_in_cooldown("stub") is True


def test_success_rate_within_window() -> None:
    clock = FakeClock()
    health = ChannelHealth(now=clock)

    health.record("stub", "echo", success=True, latency_ms=1.0)
    clock.advance(10)
    health.record("stub", "echo", success=False, latency_ms=1.0, error="timeout")
    clock.advance(10)
    health.record("stub", "echo", success=True, latency_ms=1.0)

    assert health.success_rate("stub", "echo", window_seconds=60) == pytest.approx(2 / 3)

    clock.advance(100)

    assert health.success_rate("stub", "echo", window_seconds=30) == 0.0


def test_snapshot_shape() -> None:
    health = ChannelHealth()

    health.record("stub", "echo", success=True, latency_ms=1.0)
    snapshot = health.snapshot()

    assert set(snapshot) == {"stub"}
    assert set(snapshot["stub"]) == {"echo"}
    assert set(snapshot["stub"]["echo"]) == {
        "success_count",
        "fail_count",
        "in_cooldown",
        "cooldown_until",
    }
    assert snapshot["stub"]["echo"]["success_count"] == 1
    assert snapshot["stub"]["echo"]["fail_count"] == 0
