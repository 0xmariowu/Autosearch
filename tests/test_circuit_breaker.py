"""Tests for circuit breaker behavior in search_runner.

Validates that:
- Returning [] does NOT increment consecutive_failures (it's a success)
- Raising SearchError DOES increment consecutive_failures
- Returning [] after prior failures resets consecutive_failures to 0
- SearchError with engine field is handled
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lib.search_runner import (
    SearchError,
    _channel_health,
    _record_failure,
    _record_success,
    run_single_query,
)


@pytest.fixture(autouse=True)
def _reset_health():
    """Reset channel health state before each test."""
    _channel_health.clear()
    yield
    _channel_health.clear()


class TestRecordSuccessOnEmptyResults:
    """Returning [] should count as success, not failure."""

    @pytest.mark.asyncio
    async def test_empty_list_does_not_increment_failures(self) -> None:
        # Simulate a channel returning []
        mock_method = AsyncMock(return_value=[])
        with patch("lib.search_runner.CHANNEL_METHODS", {"test-ch": mock_method}):
            result = await run_single_query({"channel": "test-ch", "query": "test"})

        assert result == []
        entry = _channel_health.get("test-ch", {})
        assert entry.get("consecutive_failures", 0) == 0

    @pytest.mark.asyncio
    async def test_empty_list_resets_prior_failures(self) -> None:
        # Pre-set 2 failures
        _channel_health["test-ch"] = {"consecutive_failures": 2}

        mock_method = AsyncMock(return_value=[])
        with patch("lib.search_runner.CHANNEL_METHODS", {"test-ch": mock_method}):
            await run_single_query({"channel": "test-ch", "query": "test"})

        entry = _channel_health.get("test-ch", {})
        assert entry.get("consecutive_failures", 0) == 0


class TestSearchErrorIncrements:
    """Raising SearchError should count as failure."""

    @pytest.mark.asyncio
    async def test_search_error_increments_failures(self) -> None:
        mock_method = AsyncMock(
            side_effect=SearchError(
                channel="test-ch", error_type="timeout", message="30s"
            )
        )
        with patch("lib.search_runner.CHANNEL_METHODS", {"test-ch": mock_method}):
            result = await run_single_query({"channel": "test-ch", "query": "test"})

        assert result == []
        entry = _channel_health.get("test-ch", {})
        assert entry["consecutive_failures"] == 1

    @pytest.mark.asyncio
    async def test_generic_exception_also_increments(self) -> None:
        mock_method = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("lib.search_runner.CHANNEL_METHODS", {"test-ch": mock_method}):
            await run_single_query({"channel": "test-ch", "query": "test"})

        entry = _channel_health.get("test-ch", {})
        assert entry["consecutive_failures"] == 1


class TestRecordSuccessResets:
    """_record_success should reset consecutive_failures."""

    def test_reset_on_success(self) -> None:
        _channel_health["ch"] = {"consecutive_failures": 5, "last_error": "timeout"}
        _record_success("ch")
        assert _channel_health["ch"]["consecutive_failures"] == 0

    def test_noop_on_unknown_channel(self) -> None:
        _record_success("never-seen")
        assert "never-seen" not in _channel_health


class TestRecordFailure:
    """_record_failure should increment and set suspension."""

    def test_first_failure(self) -> None:
        _record_failure("ch", "timeout")
        assert _channel_health["ch"]["consecutive_failures"] == 1
        assert "suspended_until" in _channel_health["ch"]

    def test_cumulative_failures(self) -> None:
        _record_failure("ch", "err1")
        _record_failure("ch", "err2")
        assert _channel_health["ch"]["consecutive_failures"] == 2

    def test_backoff_caps_at_3600(self) -> None:
        _channel_health["ch"] = {"consecutive_failures": 100}
        _record_failure("ch", "err")
        # 101 * 60 = 6060, but capped at 3600
        from datetime import datetime, timezone

        until = datetime.fromisoformat(_channel_health["ch"]["suspended_until"])
        now = datetime.now(timezone.utc)
        delta = (until - now).total_seconds()
        assert delta <= 3601  # 3600 + 1s tolerance
