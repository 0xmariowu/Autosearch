# Self-written, plan v2.3 § 13.5
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from autosearch.core.models import ClarifyResult
from autosearch.llm.client import LLMClient
from autosearch.llm.providers.anthropic import AnthropicProvider
from autosearch.llm.providers.claude_code import ClaudeCodeProvider
from autosearch.llm.providers.gemini import GeminiProvider
from autosearch.llm.providers.openai import OpenAIProvider

RUNS = 30
SPIKE_DOC_PATH = Path("docs/spikes/spike-1-auto-detect.md")
PROMPT = (
    "You are the M1 clarify step. Return JSON only. "
    "Decide whether the query 'best AI coding setup for a solo founder' needs clarification. "
    "Always include rubrics and a mode recommendation."
)


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


def _format_notes(notes: list[str]) -> str:
    if not notes:
        return "ok"
    return "<br>".join(_sanitize_cell(note) for note in notes[:3])


def _sanitize_cell(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def _write_result_row(
    provider_name: str,
    *,
    fail_count: int,
    fail_rate: float,
    notes: list[str],
) -> bool:
    if not SPIKE_DOC_PATH.exists():
        return False

    content = SPIKE_DOC_PATH.read_text(encoding="utf-8")
    if "## Result Table" not in content:
        return False

    lines = content.splitlines()
    replacement = f"| {provider_name} | {fail_count} | {fail_rate:.4f} | {_format_notes(notes)} |"

    updated = False
    for index, line in enumerate(lines):
        if line.startswith(f"| {provider_name} |"):
            lines[index] = replacement
            updated = True
            break

    if not updated:
        return False

    SPIKE_DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


@pytest.mark.asyncio
@pytest.mark.real_llm
@pytest.mark.slow
@pytest.mark.parametrize(
    "provider_name",
    ["claude_code", "anthropic", "openai", "gemini"],
)
async def test_spike_1_provider_fail_rate_under_five_percent(provider_name: str) -> None:
    _require_provider(provider_name)
    client = LLMClient(
        provider_name=provider_name,
        providers={provider_name: _build_provider(provider_name)},
    )

    failures = 0
    notes: list[str] = []

    async with asyncio.timeout(600):
        for index in range(RUNS):
            try:
                result = await client.complete(PROMPT, ClarifyResult)
                assert isinstance(result, ClarifyResult)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                notes.append(f"run {index + 1}: {type(exc).__name__}: {exc}")

    fail_rate = failures / RUNS
    _write_result_row(
        provider_name,
        fail_count=failures,
        fail_rate=fail_rate,
        notes=notes,
    )

    assert fail_rate < 0.05, (
        f"{provider_name} fail rate {fail_rate:.4f} exceeded threshold with {failures}/{RUNS} "
        "failures"
    )
