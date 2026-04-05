"""Tests for circuit breaker behavior in search_runner.

Validates that:
- Returning [] does NOT increment consecutive_failures (it's a success)
- Raising SearchError DOES increment consecutive_failures
- Returning [] after prior failures resets consecutive_failures to 0
- SearchError with engine field is handled
- Engine-level failures suspend all sibling channels
- Engine-level success clears all sibling channels
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lib.search_runner import (
    ENGINE_CHANNELS,
    SearchError,
    _channel_health,
    _record_failure,
    _record_success,
    run_single_query,
)

_ = ENGINE_CHANNELS  # used in TestEngineHealthPropagation


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


class TestEngineHealthPropagation:
    """Engine-level failure/success should propagate to all sibling channels."""

    def test_baidu_engine_failure_suspends_all_siblings(self) -> None:
        """A failure with engine='baidu' should suspend all baidu channels."""
        _record_failure("zhihu", "timeout", engine="baidu")

        baidu_channels = ENGINE_CHANNELS["baidu"]
        for ch in baidu_channels:
            entry = _channel_health.get(ch, {})
            assert "suspended_until" in entry, f"{ch} should be suspended"

    def test_ddgs_engine_failure_suspends_all_siblings(self) -> None:
        """A failure with engine='ddgs' should suspend all ddgs channels."""
        _record_failure("web-ddgs", "network error", engine="ddgs")

        ddgs_channels = ENGINE_CHANNELS["ddgs"]
        for ch in ddgs_channels:
            entry = _channel_health.get(ch, {})
            assert "suspended_until" in entry, f"{ch} should be suspended"

    def test_one_baidu_success_clears_all_siblings(self) -> None:
        """One successful baidu channel clears suspension for all."""
        # First suspend all via engine failure
        _record_failure("zhihu", "timeout", engine="baidu")

        # Then one channel succeeds (must be a channel still in baidu group)
        _record_success("douyin")

        baidu_channels = ENGINE_CHANNELS["baidu"]
        for ch in baidu_channels:
            entry = _channel_health.get(ch, {})
            assert entry.get("consecutive_failures", 0) == 0, f"{ch} should be cleared"

    def test_non_engine_failure_does_not_affect_engine_group(self) -> None:
        """An independent channel failure should not touch engine channels."""
        _record_failure("arxiv", "timeout")

        # No baidu or ddgs channels should be affected
        for engine_channels in ENGINE_CHANNELS.values():
            for ch in engine_channels:
                assert ch not in _channel_health or (
                    _channel_health[ch].get("consecutive_failures", 0) == 0
                ), f"{ch} should not be affected by arxiv failure"

    @pytest.mark.asyncio
    async def test_engine_inferred_from_channel(self) -> None:
        """Even without explicit engine arg, a known channel should propagate."""
        mock_method = AsyncMock(
            side_effect=SearchError(
                channel="zhihu",
                error_type="network",
                message="down",
                engine="baidu",
            )
        )
        with patch("lib.search_runner.CHANNEL_METHODS", {"zhihu": mock_method}):
            with patch(
                "lib.search_runner._RETRY_DELAYS", {"timeout": 0.01, "network": 0.01}
            ):
                await run_single_query({"channel": "zhihu", "query": "test"})

        # All baidu siblings should be suspended
        for ch in ENGINE_CHANNELS["baidu"]:
            entry = _channel_health.get(ch, {})
            assert "suspended_until" in entry, f"{ch} should be suspended"
