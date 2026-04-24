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
from autosearch.observability.channel_health import ChannelHealth


@dataclass
class ChannelRuntime:
    """Process-lifecycle container for the compiled channel registry + health."""

    registry: ChannelRegistry | None
    health: ChannelHealth
    # Channels exposed for the v2 happy-path tools (filtered by `available()`)
    channels: list[Channel]


_runtime: ChannelRuntime | None = None
_runtime_lock = threading.Lock()


def get_channel_runtime() -> ChannelRuntime:
    """Return the shared runtime, building it on first access. Thread-safe."""
    global _runtime
    if _runtime is None:
        with _runtime_lock:
            if _runtime is None:
                _runtime = _build()
    return _runtime


def reset_channel_runtime() -> None:
    """Drop the cached runtime so the next `get_channel_runtime()` rebuilds.

    Tests use this between scenarios that monkeypatch channel sources or env
    state. Production code never calls it.
    """
    global _runtime
    with _runtime_lock:
        _runtime = None


def install_test_runtime(channels: list[Channel], registry: ChannelRegistry | None = None) -> None:
    """Install a pre-built runtime for tests that need to inject specific
    channels (replacing the discovery-from-skills path). Pairs with
    `reset_channel_runtime()` in autouse fixtures."""
    global _runtime
    with _runtime_lock:
        _runtime = ChannelRuntime(
            registry=registry, health=ChannelHealth(), channels=list(channels)
        )


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
    registry = _build_registry()
    if registry is not None:
        registry.attach_health(health)

    channels = build_channels_fn()
    # When the registry exists in production, prefer its filtered list so
    # availability state stays consistent. Tests that injected a custom
    # build_channels_fn keep their channels untouched.
    if registry is not None and build_channels_fn.__module__ == "autosearch.core.channel_bootstrap":
        channels = registry.available() or [DemoChannel()]

    return ChannelRuntime(registry=registry, health=health, channels=channels)
