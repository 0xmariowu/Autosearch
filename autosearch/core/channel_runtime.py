"""Shared, server-lifecycle channel runtime.

Plan §P0-5: `_build_channels()` was being called per `run_channel` MCP tool
invocation, which created a fresh `ChannelRegistry` and a fresh `ChannelHealth`
every time. Cooldown / failure-rate state was destroyed between calls, so the
circuit breaker (#314) was structurally wired but functionally a no-op.

This module owns ONE compiled registry + ONE `ChannelHealth` for the lifetime
of the process. MCP tools and CLI commands look up channels through it instead
of rebuilding.

`reset()` is provided for tests that need to swap in a stub registry; the
production path never calls it.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from autosearch.channels.base import Channel, ChannelRegistry
from autosearch.core.rate_limiter import RateLimiter
from autosearch.observability.channel_health import ChannelHealth


@dataclass
class ChannelRuntime:
    """Process-lifecycle container for the compiled channel registry + health
    + rate limiter — all the per-process state that needs to outlive a single
    MCP tool call so cooldowns and rate limits actually accumulate."""

    registry: ChannelRegistry | None
    health: ChannelHealth
    limiter: RateLimiter
    # Channels exposed for the v2 happy-path tools (filtered by `available()`)
    channels: list[Channel]


_runtime: ChannelRuntime | None = None
_runtime_fingerprint: tuple | None = None
_runtime_lock = threading.Lock()

# Channel-relevant env keys whose presence/absence flips channel availability.
# When any of these appears or disappears (or the secrets file mtime changes),
# the runtime must rebuild so `doctor` and `run_channel` agree in the same MCP
# process (Bug 1 / fix-plan).
_CHANNEL_ENV_KEYS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "CLAUDE_API_KEY",
    "YOUTUBE_API_KEY",
    "TIKHUB_API_KEY",
    "FIRECRAWL_API_KEY",
    "OPENROUTER_API_KEY",
    "SEARXNG_URL",
    "AUTOSEARCH_SIGNSRV_URL",
    "AUTOSEARCH_SERVICE_TOKEN",
    "XHS_A1_COOKIE",
    "XHS_COOKIES",
    "XIAOHONGSHU_COOKIES",
    "TWITTER_COOKIES",
    "BILIBILI_COOKIES",
    "WEIBO_COOKIES",
    "DOUYIN_COOKIES",
    "ZHIHU_COOKIES",
    "XUEQIU_COOKIES",
)


def _current_fingerprint() -> tuple:
    """Build a fingerprint that flips when secrets-file mtime or any
    channel-relevant env-key presence changes.

    Cheap to compute (one `stat` + a small set membership) so it can run on
    every `get_channel_runtime()` call.
    """
    import os  # noqa: PLC0415

    from autosearch.core.secrets_store import secrets_path  # noqa: PLC0415

    try:
        path = secrets_path()
        mtime = path.stat().st_mtime if path.exists() else None
    except OSError:
        mtime = None
    env_presence = tuple(sorted(k for k in _CHANNEL_ENV_KEYS if os.environ.get(k)))
    return (mtime, env_presence)


def get_channel_runtime() -> ChannelRuntime:
    """Return the shared runtime, rebuilding when secrets/env fingerprint changes.

    Thread-safe. Bug 1 (fix-plan): a long-running MCP process used to keep its
    first-load runtime forever, so `autosearch configure NEW_KEY` written by
    the user *while the MCP host was open* never reached `run_channel` — even
    though `doctor` (which re-scans every call) saw it. Now both agree.
    """
    global _runtime, _runtime_fingerprint
    fp = _current_fingerprint()
    if _runtime is None or _runtime_fingerprint != fp:
        with _runtime_lock:
            fp = _current_fingerprint()
            if _runtime is None or _runtime_fingerprint != fp:
                # Re-inject secrets-file values into env BEFORE rebuilding the
                # registry so newly added keys are visible to availability
                # checks. Bug 2 (fix-plan): force=True so `configure --replace`
                # actually overwrites the value previously injected from the
                # file — without this the long-running MCP process keeps the
                # stale value even though mtime / fingerprint did flip.
                try:
                    from autosearch.core.secrets_store import (  # noqa: PLC0415
                        inject_into_env,
                    )

                    inject_into_env(force=True)
                except Exception:  # noqa: BLE001
                    pass
                fp = _current_fingerprint()
                _runtime = _build()
                _runtime_fingerprint = fp
    return _runtime


def reset_channel_runtime() -> None:
    """Drop the cached runtime so the next `get_channel_runtime()` rebuilds.

    Tests use this between scenarios that monkeypatch channel sources or env
    state. Production code does not need to call it — the fingerprint check
    above handles legitimate secrets-file changes.
    """
    global _runtime, _runtime_fingerprint
    with _runtime_lock:
        _runtime = None
        _runtime_fingerprint = None


def install_test_runtime(channels: list[Channel], registry: ChannelRegistry | None = None) -> None:
    """Install a pre-built runtime for tests that need to inject specific
    channels (replacing the discovery-from-skills path). Pairs with
    `reset_channel_runtime()` in autouse fixtures."""
    global _runtime, _runtime_fingerprint
    with _runtime_lock:
        _runtime = ChannelRuntime(
            registry=registry,
            health=ChannelHealth(),
            limiter=RateLimiter(),
            channels=list(channels),
        )
        # Pin the fingerprint so the next get_channel_runtime() doesn't
        # rebuild over the test's injected channels.
        _runtime_fingerprint = _current_fingerprint()


def _build() -> ChannelRuntime:
    # Lazy imports so this module can be imported cheaply (e.g. from CLI
    # startup) without dragging in the full channel surface.
    from autosearch.channels.demo import DemoChannel
    from autosearch.core.channel_bootstrap import _build_registry

    # Resolve `_build_channels` through `autosearch.mcp.server` when that
    # module is loaded, because existing tests monkeypatch the attribute
    # there. In production both paths point to the same callable since
    # `mcp.server` imports `_build_channels` at module load.
    build_channels_fn = None
    try:
        import sys

        server_mod = sys.modules.get("autosearch.mcp.server")
        if server_mod is not None:
            build_channels_fn = getattr(server_mod, "_build_channels", None)
    except Exception:
        build_channels_fn = None
    if build_channels_fn is None:
        from autosearch.core.channel_bootstrap import _build_channels as build_channels_fn

    health = ChannelHealth()
    limiter = RateLimiter()
    registry = _build_registry()
    if registry is not None:
        registry.attach_health(health)
        registry.attach_limiter(limiter)

    channels = build_channels_fn()
    # When the registry exists in production, prefer its filtered list so
    # availability state stays consistent. Tests that injected a custom
    # build_channels_fn keep their channels untouched.
    if registry is not None and build_channels_fn.__module__ == "autosearch.core.channel_bootstrap":
        channels = registry.available() or [DemoChannel()]

    return ChannelRuntime(registry=registry, health=health, limiter=limiter, channels=channels)
