"""Bugs 1/2/3 (fix-plan v8 follow-up): pin three remaining typed-error
contracts that the channel batch (#355) missed.

- Bug 1: youtube data_api_v3's first `except httpx.HTTPStatusError` block
  used to log auth_failed but still return [], so a bad key looked like no
  matches. Now propagates as ChannelAuthError.
- Bug 2: xiaohongshu/bilibili/linkedin had INNER `except: return []` that
  short-circuited the registry's fallback chain (base.py treats [] as
  success and stops). They now raise typed errors so via_tikhub fallbacks
  actually run.
- Bug 3: TikHub 401 was missing from `_error_for_status`'s auth bucket;
  402 (budget exhausted) was lumped into rate_limited. Both fixed."""

from __future__ import annotations

import pytest

import autosearch.mcp.server as mcp_server
from autosearch.channels.base import (
    BudgetExhausted,
    ChannelAuthError,
    RateLimited,
)
from autosearch.core.channel_runtime import reset_channel_runtime
from autosearch.lib.tikhub_client import (
    TikhubBudgetExhausted,
    TikhubError,
    TikhubRateLimited,
    TikhubUpstreamError,
    to_channel_error,
)


def test_tikhub_401_maps_to_channel_auth_error() -> None:
    """Bug 3: a stale TIKHUB_API_KEY (401) used to surface as channel_error."""
    exc = TikhubUpstreamError("auth", status_code=401, detail={"reason": "invalid_key"})
    assert isinstance(to_channel_error(exc), ChannelAuthError)


def test_tikhub_402_maps_to_budget_exhausted() -> None:
    """Bug 3: 402 means top-up, not wait-and-retry. Distinct from RateLimited."""
    exc = TikhubBudgetExhausted("paid", status_code=402, detail={"reason": "wallet"})
    result = to_channel_error(exc)
    assert isinstance(result, BudgetExhausted)
    assert not isinstance(result, RateLimited)


def test_tikhub_429_still_maps_to_rate_limited() -> None:
    """Sanity: rate limit (429) keeps its own status, separate from 402."""
    exc = TikhubRateLimited("burst", status_code=429, detail={"reason": "burst"})
    assert isinstance(to_channel_error(exc), RateLimited)


def test_tikhub_unknown_error_falls_to_transient() -> None:
    """Sanity: catch-all path still produces a typed transient (no escape)."""
    from autosearch.channels.base import TransientError

    exc = TikhubError("upstream gateway oops")
    assert isinstance(to_channel_error(exc), TransientError)


class _RaisingChannel:
    languages = ["en"]

    def __init__(self, name: str, exc: Exception) -> None:
        self.name = name
        self._exc = exc

    async def search(self, _query):  # noqa: ANN001
        raise self._exc


@pytest.fixture
def _stub_channel(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(tmp_path / "experience"))
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "missing-secrets.env"))
    reset_channel_runtime()

    def _set(channel) -> None:
        monkeypatch.setattr(mcp_server, "_build_channels", lambda: [channel])
        reset_channel_runtime()

    yield _set
    reset_channel_runtime()


@pytest.mark.asyncio
async def test_budget_exhausted_returns_status_budget_exhausted(_stub_channel) -> None:
    """Bug 3: status='budget_exhausted' is a distinct value, not rate_limited."""
    _stub_channel(_RaisingChannel("youtube", BudgetExhausted("TikHub balance: $0")))
    server = mcp_server.create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    result = await server._tool_manager.call_tool(
        "run_channel", {"channel_name": "youtube", "query": "anything"}
    )
    assert result.ok is False
    assert result.status == "budget_exhausted"
