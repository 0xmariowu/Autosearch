# Self-written, plan v2.3 § 13.5
import asyncio
import json
import os
import shutil
import subprocess

import pytest
from pydantic import BaseModel

from autosearch.llm.client import LLMClient
from autosearch.llm.providers.anthropic import AnthropicProvider
from autosearch.llm.providers.claude_code import ClaudeCodeProvider
from autosearch.llm.providers.gemini import GeminiProvider
from autosearch.llm.providers.openai import OpenAIProvider


class Greeting(BaseModel):
    text: str
    score: int


def _claude_code_unavailable_reason() -> str | None:
    if shutil.which("claude") is None:
        return "claude binary not found on PATH"

    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError as exc:
        return f"claude auth status unavailable: {exc}"

    payload = result.stdout.strip() or result.stderr.strip()
    if payload:
        try:
            auth_status = json.loads(payload)
        except json.JSONDecodeError:
            auth_status = None
        if isinstance(auth_status, dict) and auth_status.get("loggedIn") is True:
            return None
        if isinstance(auth_status, dict) and auth_status.get("loggedIn") is False:
            return "claude auth status reports loggedIn=false"

    return "claude auth status unavailable"


def _require_provider(provider_name: str) -> None:
    if provider_name == "claude_code":
        unavailable_reason = _claude_code_unavailable_reason()
        if unavailable_reason is not None:
            pytest.skip(unavailable_reason)
        return

    requirements = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
    }
    env_var = requirements[provider_name]
    if not os.getenv(env_var):
        pytest.skip(f"{env_var} not set")


def _build_provider(provider_name: str) -> object:
    if provider_name == "claude_code":
        return ClaudeCodeProvider()
    if provider_name == "anthropic":
        return AnthropicProvider()
    if provider_name == "openai":
        return OpenAIProvider()
    if provider_name == "gemini":
        return GeminiProvider()
    raise ValueError(f"Unknown provider: {provider_name}")


@pytest.mark.asyncio
@pytest.mark.real_llm
@pytest.mark.parametrize(
    "provider_name",
    ["claude_code", "anthropic", "openai", "gemini"],
)
async def test_provider_roundtrip_structured_output(provider_name: str) -> None:
    _require_provider(provider_name)
    client = LLMClient(
        provider_name=provider_name,
        providers={provider_name: _build_provider(provider_name)},
    )

    async with asyncio.timeout(30):
        result = await client.complete(
            (
                "Return JSON only. "
                "Set text to a short greeting for the AutoSearch test harness and score to an "
                "integer confidence score."
            ),
            Greeting,
        )

    assert isinstance(result, Greeting)
    assert result.text.strip()
    assert isinstance(result.score, int)
