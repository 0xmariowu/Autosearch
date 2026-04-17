# Self-written, plan v2.3 § 13.5
import asyncio
import json
import os
import shutil
import subprocess

import pytest

from autosearch.channels.demo import DemoChannel
from autosearch.core.pipeline import Pipeline
from autosearch.llm.client import LLMClient
from autosearch.llm.providers.anthropic import AnthropicProvider
from autosearch.llm.providers.claude_code import ClaudeCodeProvider
from autosearch.llm.providers.gemini import GeminiProvider
from autosearch.llm.providers.openai import OpenAIProvider
from autosearch.observability.cost import CostTracker


def _claude_code_available() -> bool:
    if shutil.which("claude") is None:
        return False

    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError:
        return False

    payload = result.stdout.strip() or result.stderr.strip()
    if not payload:
        return False

    try:
        auth_status = json.loads(payload)
    except json.JSONDecodeError:
        return False
    return isinstance(auth_status, dict) and auth_status.get("loggedIn") is True


def _select_available_provider() -> str | None:
    if _claude_code_available():
        return "claude_code"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    return None


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
async def test_pipeline_demo_roundtrip_uses_real_llm() -> None:
    provider_name = _select_available_provider()
    if provider_name is None:
        pytest.skip("No real LLM provider available in this environment")

    cost_tracker = CostTracker()
    llm = LLMClient(
        provider_name=provider_name,
        providers={provider_name: _build_provider(provider_name)},
        cost_tracker=cost_tracker,
    )
    pipeline = Pipeline(llm=llm, channels=[DemoChannel()])

    async with asyncio.timeout(300):
        result = await pipeline.run("retrieval augmented generation")
        if result.status == "needs_clarification":
            # Some providers treat the bare phrase as underspecified. Retry once with an explicit
            # report request instead of looping indefinitely.
            result = await pipeline.run(
                "Write a concise research report about retrieval augmented generation, "
                "covering what it is, key architecture tradeoffs, and cited sources."
            )

    assert result.status == "ok"
    assert result.markdown is not None
    assert "## References" in result.markdown
    assert "## Sources" in result.markdown
    assert any(line.startswith("#") for line in result.markdown.splitlines())
    assert result.cost >= 0.0
    assert result.prompt_tokens + result.completion_tokens > 0
