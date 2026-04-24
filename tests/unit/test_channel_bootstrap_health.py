"""Pin the contract that `_build_channels` attaches a runtime ChannelHealth.

Without this wiring the circuit breaker is dead code: `_record_health` calls
inside `_CompiledChannel.search` no-op because `_health_provider` returns None,
and `available()` cannot filter cooled-down channels.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from autosearch.channels.base import ChannelRegistry, Environment
from autosearch.core.channel_bootstrap import _build_channels


def _write_skill(root: Path, name: str = "live_chan") -> None:
    skill = root / name
    (skill / "methods").mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        dedent(
            f"""
            ---
            name: {name}
            description: "Fixture skill for bootstrap test."
            version: 1
            languages: [en]
            methods:
              - id: echo
                impl: methods/echo.py
                requires: []
            fallback_chain: [echo]
            ---
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (skill / "methods" / "echo.py").write_text(
        dedent(
            """
            from datetime import UTC, datetime

            from autosearch.core.models import Evidence, SubQuery


            async def search(query: SubQuery) -> list[Evidence]:
                return [
                    Evidence(
                        url="https://example.com/echo",
                        title="echo",
                        snippet="",
                        source_channel="live_chan:echo",
                        fetched_at=datetime.now(UTC),
                    )
                ]
            """
        ).lstrip(),
        encoding="utf-8",
    )


def test_build_channels_attaches_runtime_channel_health(monkeypatch, tmp_path):
    monkeypatch.delenv("AUTOSEARCH_LLM_MODE", raising=False)

    root = tmp_path / "channels"
    _write_skill(root)

    captured: dict[str, object] = {}
    real_attach = ChannelRegistry.attach_health

    def _spy_attach(self, health):
        captured["health"] = health
        return real_attach(self, health)

    monkeypatch.setattr(ChannelRegistry, "attach_health", _spy_attach)

    channels = _build_channels(channels_root=root, env=Environment())

    assert "health" in captured, (
        "_build_channels must call ChannelRegistry.attach_health so the circuit "
        "breaker is reachable from runtime channel calls"
    )
    assert captured["health"] is not None
    assert channels  # something was returned (registry produced a channel)


@pytest.mark.asyncio
async def test_build_channels_health_records_call_outcomes(monkeypatch, tmp_path):
    """End-to-end: a successful channel call must register in the attached health
    snapshot. Proves the wiring is live, not just a dangling reference."""
    monkeypatch.delenv("AUTOSEARCH_LLM_MODE", raising=False)

    root = tmp_path / "channels"
    _write_skill(root)

    captured: dict[str, object] = {}
    real_attach = ChannelRegistry.attach_health

    def _spy_attach(self, health):
        captured["health"] = health
        return real_attach(self, health)

    monkeypatch.setattr(ChannelRegistry, "attach_health", _spy_attach)

    channels = _build_channels(channels_root=root, env=Environment())
    target = next(c for c in channels if c.name == "live_chan")

    from autosearch.core.models import SubQuery

    await target.search(SubQuery(text="ping", rationale="bootstrap-health spike"))

    snapshot = captured["health"].snapshot()
    assert "live_chan" in snapshot, "ChannelHealth did not record the executed call"
    assert snapshot["live_chan"]["echo"]["success_count"] == 1
