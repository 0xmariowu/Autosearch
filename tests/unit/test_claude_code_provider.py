"""Tests for ClaudeCodeProvider."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

import autosearch.llm.providers.claude_code as claude_code_mod
from autosearch.llm.providers.claude_code import ClaudeCodeProvider


class _ResponseModel(BaseModel):
    result: str


class _FakeProcess:
    returncode = 0

    async def communicate(self) -> tuple[bytes, bytes]:
        return b'{"result":"ok"}', b""


@pytest.mark.asyncio
async def test_claude_code_subprocess_receives_minimal_env(monkeypatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("TIKHUB_API_KEY", "secret")
    monkeypatch.setenv("XHS_COOKIES", "cookie")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic")

    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr(ClaudeCodeProvider, "is_available", staticmethod(lambda: True))
    monkeypatch.setattr(
        claude_code_mod.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    result = await ClaudeCodeProvider().complete("prompt", _ResponseModel)

    assert result == "ok"
    env = captured["kwargs"]["env"]
    assert env["ANTHROPIC_API_KEY"] == "anthropic"
    assert env["PATH"] == "/usr/bin"
    assert "TIKHUB_API_KEY" not in env
    assert "XHS_COOKIES" not in env
