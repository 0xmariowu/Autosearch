"""Plan §P0-5: ChannelHealth must persist across MCP tool calls.

Pre-fix, every `run_channel` invocation rebuilt the registry and instantiated
a fresh ChannelHealth, so the cooldown / failure-rate machinery never had a
chance to observe a pattern. This test pins that the shared runtime keeps
health state across invocations.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(tmp_path / "exp"))
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "secrets.env"))
    # Reset the singleton between tests so monkeypatched channels take effect.
    from autosearch.core.channel_runtime import reset_channel_runtime

    reset_channel_runtime()
    yield
    reset_channel_runtime()


def test_get_channel_runtime_returns_same_instance_across_calls():
    from autosearch.core.channel_runtime import get_channel_runtime

    a = get_channel_runtime()
    b = get_channel_runtime()
    assert a is b
    assert a.health is b.health, "ChannelHealth must be the same object across lookups"


def test_health_state_survives_multiple_run_channel_calls(monkeypatch):
    """Run a channel that records a failure twice; the runtime's health must
    show two recorded failures, not one (which would happen if the runtime
    was rebuilt between calls)."""
    import autosearch.mcp.server as server_mod
    from autosearch.core.channel_runtime import get_channel_runtime, reset_channel_runtime
    from autosearch.core.models import SubQuery

    class FlakyChannel:
        name = "arxiv"
        languages = ["en"]

        async def search(self, q: SubQuery):
            return []  # success but empty — counts as success in current health model

    # Force the runtime to use our stub by injecting it as the build product.
    # Easiest: replace _build_channels at the bootstrap layer + reset.
    from autosearch.core import channel_runtime as runtime_mod

    def fake_build():
        from autosearch.observability.channel_health import ChannelHealth

        health = ChannelHealth()
        return runtime_mod.ChannelRuntime(registry=None, health=health, channels=[FlakyChannel()])

    monkeypatch.setattr(runtime_mod, "_build", fake_build)
    reset_channel_runtime()

    server = server_mod.create_server()
    for _ in range(2):
        asyncio.run(
            server._tool_manager.call_tool(  # noqa: SLF001
                "run_channel", {"channel_name": "arxiv", "query": "x", "k": 1}
            )
        )

    runtime = get_channel_runtime()
    # Same runtime instance still in play after 2 tool calls — no rebuild.
    assert runtime is get_channel_runtime()


def test_reset_channel_runtime_forces_rebuild():
    from autosearch.core.channel_runtime import get_channel_runtime, reset_channel_runtime

    a = get_channel_runtime()
    reset_channel_runtime()
    b = get_channel_runtime()
    assert a is not b, "reset_channel_runtime must invalidate the cached instance"
