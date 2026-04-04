"""Tests for transient failure retry logic in search_runner.

Validates that:
- Transient errors (timeout, network) are retried once
- Non-transient errors (rate_limit, auth, parse) are NOT retried
- Retry succeeds on second attempt
- Retry fails and records to circuit breaker
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lib.search_runner import (
    SearchError,
    _channel_health,
    run_single_query,
)


@pytest.fixture(autouse=True)
def _reset_health():
    _channel_health.clear()
    yield
    _channel_health.clear()


class TestTransientRetry:
    """Transient errors should be retried once."""

    @pytest.mark.asyncio
    async def test_timeout_retried_and_succeeds(self) -> None:
        """First call times out, second succeeds."""
        mock_method = AsyncMock(
            side_effect=[
                SearchError(channel="ch", error_type="timeout", message="30s"),
                [{"url": "http://x.com", "title": "ok"}],
            ]
        )
        with patch("lib.search_runner.CHANNEL_METHODS", {"ch": mock_method}):
            with patch(
                "lib.search_runner._RETRY_DELAYS", {"timeout": 0.01, "network": 0.01}
            ):
                result = await run_single_query({"channel": "ch", "query": "test"})

        assert len(result) == 1
        assert mock_method.call_count == 2
        # Should be recorded as success (retry worked)
        entry = _channel_health.get("ch", {})
        assert entry.get("consecutive_failures", 0) == 0

    @pytest.mark.asyncio
    async def test_network_error_retried_and_succeeds(self) -> None:
        """First call has network error, second succeeds."""
        mock_method = AsyncMock(
            side_effect=[
                SearchError(channel="ch", error_type="network", message="reset"),
                [{"url": "http://x.com", "title": "ok"}],
            ]
        )
        with patch("lib.search_runner.CHANNEL_METHODS", {"ch": mock_method}):
            with patch(
                "lib.search_runner._RETRY_DELAYS", {"timeout": 0.01, "network": 0.01}
            ):
                result = await run_single_query({"channel": "ch", "query": "test"})

        assert len(result) == 1
        assert mock_method.call_count == 2

    @pytest.mark.asyncio
    async def test_transient_retry_fails_records_failure(self) -> None:
        """Both attempts fail — should record to circuit breaker."""
        mock_method = AsyncMock(
            side_effect=[
                SearchError(channel="ch", error_type="timeout", message="1st"),
                SearchError(channel="ch", error_type="timeout", message="2nd"),
            ]
        )
        with patch("lib.search_runner.CHANNEL_METHODS", {"ch": mock_method}):
            with patch(
                "lib.search_runner._RETRY_DELAYS", {"timeout": 0.01, "network": 0.01}
            ):
                result = await run_single_query({"channel": "ch", "query": "test"})

        assert result == []
        assert mock_method.call_count == 2
        entry = _channel_health.get("ch", {})
        assert entry["consecutive_failures"] == 1  # only recorded once (on final fail)


class TestNonTransientNoRetry:
    """Non-transient errors should NOT be retried."""

    @pytest.mark.asyncio
    async def test_rate_limit_not_retried(self) -> None:
        mock_method = AsyncMock(
            side_effect=SearchError(
                channel="ch", error_type="rate_limit", message="429"
            )
        )
        with patch("lib.search_runner.CHANNEL_METHODS", {"ch": mock_method}):
            result = await run_single_query({"channel": "ch", "query": "test"})

        assert result == []
        assert mock_method.call_count == 1  # no retry
        assert _channel_health["ch"]["consecutive_failures"] == 1

    @pytest.mark.asyncio
    async def test_auth_not_retried(self) -> None:
        mock_method = AsyncMock(
            side_effect=SearchError(channel="ch", error_type="auth", message="401")
        )
        with patch("lib.search_runner.CHANNEL_METHODS", {"ch": mock_method}):
            result = await run_single_query({"channel": "ch", "query": "test"})

        assert result == []
        assert mock_method.call_count == 1

    @pytest.mark.asyncio
    async def test_parse_not_retried(self) -> None:
        mock_method = AsyncMock(
            side_effect=SearchError(
                channel="ch", error_type="parse", message="bad json"
            )
        )
        with patch("lib.search_runner.CHANNEL_METHODS", {"ch": mock_method}):
            result = await run_single_query({"channel": "ch", "query": "test"})

        assert result == []
        assert mock_method.call_count == 1
