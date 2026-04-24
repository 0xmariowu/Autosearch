"""Plan §P0-3: a known-but-unconfigured channel must return `not_configured`,
NOT `unknown_channel`.

Without this contract, the host agent gets an "unknown channel — available: ..."
error and either gives up or routes to the wrong channel, instead of asking
the user to configure the missing key.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _isolated_runtime(tmp_path, monkeypatch):
    """Keep the test's writes out of the user's home and out of the package tree."""
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(tmp_path / "experience"))
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "missing-secrets.env"))


def _call_run_channel(channel_name: str):
    from autosearch.mcp.server import create_server

    server = create_server()
    return asyncio.run(
        server._tool_manager.call_tool(  # noqa: SLF001
            "run_channel", {"channel_name": channel_name, "query": "test", "k": 1}
        )
    )


def _payload(result) -> dict:
    """Extract the structured RunChannelResponse from FastMCP's wrapper."""
    if hasattr(result, "structured_content") and result.structured_content:
        return result.structured_content
    if hasattr(result, "content"):
        for c in result.content:
            if hasattr(c, "text"):
                import json

                return json.loads(c.text)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def test_youtube_without_key_returns_not_configured_not_unknown(monkeypatch):
    """The smoking gun: YOUTUBE_API_KEY is unset, the secrets file is empty,
    youtube is a real channel — must surface `not_configured` + the env it
    needs, not `unknown_channel`."""
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

    payload = _payload(_call_run_channel("youtube"))

    assert payload["ok"] is False
    assert payload["status"] == "not_configured", (
        f"expected not_configured, got {payload['status']}: {payload}"
    )
    assert any("YOUTUBE_API_KEY" in u for u in payload["unmet_requires"]), (
        f"unmet_requires must surface YOUTUBE_API_KEY: {payload['unmet_requires']}"
    )
    # fix_hint should help the agent ask the user for the right command
    fix_hint = payload.get("fix_hint") or ""
    assert "YOUTUBE_API_KEY" in fix_hint or "configure" in fix_hint.lower(), (
        f"fix_hint must point to the configure command: {fix_hint!r}"
    )


def test_typo_channel_name_returns_unknown_channel():
    """Genuinely unknown name still gets unknown_channel — but with the new
    `status` field so the agent can branch on it cleanly."""
    payload = _payload(_call_run_channel("not-a-real-channel-xyz"))

    assert payload["ok"] is False
    assert payload["status"] == "unknown_channel"
    # unknown_channel must NOT include unmet_requires (nothing meaningful to say)
    assert payload["unmet_requires"] == []
