"""Plan §P0-4: secret-looking strings must NOT appear in MCP tool responses.

A channel library, an upstream HTTP error, or an accidental traceback can
include `Bearer sk-…` text. If that text gets piped into the MCP `reason`
field unredacted, every host-agent transcript and every issue paste leaks
a credential.

The fix is to apply `core.redact.redact()` at every CLI/MCP boundary that
constructs a string from arbitrary upstream content.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(tmp_path / "exp"))
    monkeypatch.setenv("AUTOSEARCH_SECRETS_FILE", str(tmp_path / "missing-secrets.env"))


def _payload(result) -> dict:
    if hasattr(result, "structured_content") and result.structured_content:
        return result.structured_content
    if hasattr(result, "content"):
        for c in result.content:
            if hasattr(c, "text"):
                import json

                return json.loads(c.text)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def test_run_channel_redacts_bearer_token_in_channel_error(monkeypatch):
    """A channel that raises with a Bearer-shaped token in the message must
    not leak that token into the MCP response."""
    from autosearch.core.models import SubQuery
    import autosearch.mcp.server as server_mod

    class LeakyChannel:
        name = "arxiv"
        languages = ["en"]

        async def search(self, q: SubQuery):
            raise RuntimeError(
                "upstream rejected Authorization: Bearer sk-ant-LEAKED-VALUE-12345-ABCDE"
            )

    monkeypatch.setattr(server_mod, "_build_channels", lambda: [LeakyChannel()])
    server = server_mod.create_server()
    result = asyncio.run(
        server._tool_manager.call_tool(  # noqa: SLF001
            "run_channel", {"channel_name": "arxiv", "query": "BM25", "k": 1}
        )
    )
    payload = _payload(result)

    assert payload["ok"] is False
    assert payload["status"] == "channel_error"
    reason = payload.get("reason") or ""
    assert "sk-ant-LEAKED" not in reason, f"secret leaked into reason: {reason!r}"
    assert "Bearer sk-ant" not in reason
    assert "REDACTED" in reason or "[REDACTED]" in reason


def test_experience_event_query_is_redacted_before_write(tmp_path, monkeypatch):
    """An agent might accidentally pass a query containing a Bearer token
    (e.g. summarizing an HTTP request). The persisted patterns.jsonl must
    not store the raw secret."""
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(tmp_path / "exp"))
    from autosearch.skills import experience as exp_mod

    # Fake skill_dir resolution
    monkeypatch.setattr(
        exp_mod,
        "_runtime_skill_dir",
        lambda name: tmp_path / "exp" / "channels" / name,
    )
    exp_mod.append_event(
        "arxiv",
        {
            "skill": "arxiv",
            "query": "tell me about Authorization: Bearer sk-ant-secretvalue123456",
            "outcome": "success",
        },
    )

    patterns = (
        tmp_path / "exp" / "channels" / "arxiv" / "experience" / "patterns.jsonl"
    ).read_text(encoding="utf-8")
    assert "sk-ant-secretvalue" not in patterns
    assert "REDACTED" in patterns
