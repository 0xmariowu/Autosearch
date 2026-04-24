"""Bug 1 (fix-plan): when a channel raises a typed error
(`ChannelAuthError`, `RateLimited`, anything else), `run_channel` returns a
distinct `status` so the host agent knows the difference between
"actually no results" and "the channel is broken / rate-limited / 401".

Pre-fix: every channel did `except Exception: return []`, so failures looked
identical to legit empty results (`status="no_results"`)."""

from __future__ import annotations

import pytest

import autosearch.mcp.server as mcp_server
from autosearch.channels.base import ChannelAuthError, RateLimited
from autosearch.core.channel_runtime import reset_channel_runtime


class _RaisingChannel:
    """Test channel that raises a configurable exception on every search()."""

    languages = ["en"]

    def __init__(self, name: str, exc: Exception) -> None:
        self.name = name
        self._exc = exc

    async def search(self, _query):  # noqa: ANN001
        raise self._exc


class _EmptyChannel:
    languages = ["en"]

    def __init__(self, name: str) -> None:
        self.name = name

    async def search(self, _query):  # noqa: ANN001
        return []


@pytest.fixture
def _stub_channel(monkeypatch, tmp_path):
    """Replace _build_channels so run_channel sees only the stubbed channel."""
    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(tmp_path / "experience"))
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "missing-secrets.env"))
    reset_channel_runtime()

    def _set(channel) -> None:
        monkeypatch.setattr(mcp_server, "_build_channels", lambda: [channel])
        reset_channel_runtime()

    yield _set
    reset_channel_runtime()


async def _call_run_channel(channel_name: str):
    server = mcp_server.create_server(pipeline_factory=lambda: None)  # type: ignore[arg-type]
    return await server._tool_manager.call_tool(
        "run_channel", {"channel_name": channel_name, "query": "anything"}
    )


@pytest.mark.asyncio
async def test_auth_failure_returns_status_auth_failed(_stub_channel) -> None:
    _stub_channel(_RaisingChannel("github", ChannelAuthError("HTTP 403")))
    result = await _call_run_channel("github")
    assert result.ok is False
    assert result.status == "auth_failed", (
        f"expected status='auth_failed', got '{result.status}' (Bug 1: a 401/403 "
        "must NOT be reported as no_results / channel_error)"
    )


@pytest.mark.asyncio
async def test_rate_limit_returns_status_rate_limited(_stub_channel) -> None:
    _stub_channel(_RaisingChannel("github", RateLimited("HTTP 429")))
    result = await _call_run_channel("github")
    assert result.ok is False
    assert result.status == "rate_limited"


@pytest.mark.asyncio
async def test_unknown_exception_returns_status_channel_error(_stub_channel) -> None:
    _stub_channel(_RaisingChannel("github", RuntimeError("upstream went sideways")))
    result = await _call_run_channel("github")
    assert result.ok is False
    assert result.status == "channel_error"


@pytest.mark.asyncio
async def test_real_empty_result_still_reports_no_results(_stub_channel) -> None:
    """Sanity: a channel that legitimately returns [] is no_results, not an error."""
    _stub_channel(_EmptyChannel("github"))
    result = await _call_run_channel("github")
    assert result.ok is True
    assert result.status == "no_results"
