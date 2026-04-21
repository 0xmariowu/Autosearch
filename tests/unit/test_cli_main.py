import httpx
import pytest
from typer.testing import CliRunner

from autosearch.cli import main as cli_main
import autosearch.llm.client as client_module

runner = CliRunner()


def _auth_error() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(401, request=request)
    return httpx.HTTPStatusError("401 Unauthorized", request=request, response=response)


def test_cli_exits_nonzero_without_any_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env_var in (
        "AUTOSEARCH_LLM_MODE",
        "AUTOSEARCH_LLM_PROVIDER",
        "AUTOSEARCH_PROVIDER_CHAIN",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "CLAUDE_API_KEY",
    ):
        monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setattr(
        client_module.ClaudeCodeProvider,
        "is_available",
        staticmethod(lambda: False),
    )

    result = runner.invoke(cli_main.app, ["query", "test", "--no-stream"])

    assert result.exit_code != 0
    assert "No LLM provider available" in result.stderr


def test_cli_exits_nonzero_with_invalid_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # W3.3 PR D: Pipeline.run raises NotImplementedError pointing at the v2
    # trio. The CLI query path now surfaces the deprecation message instead
    # of the LLM auth failure. Assertion updated to match new legacy-path
    # behavior (CLI exits non-zero, stderr mentions the migration).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-invalid-fake-xxx")
    monkeypatch.setattr(cli_main, "_build_channels", lambda: [])
    monkeypatch.setattr(cli_main.LLMClient, "complete", _raise_auth_error)

    result = runner.invoke(cli_main.app, ["query", "test", "--no-stream"])

    assert result.exit_code != 0
    assert (
        "Pipeline is removed" in result.stderr
        or "list_skills" in result.stderr
        or "NotImplementedError" in result.stderr
    )


def test_cli_rejects_empty_query() -> None:
    result = runner.invoke(cli_main.app, ["query", ""])

    assert result.exit_code == 2
    assert result.stderr == "Query must not be empty.\n"


async def _raise_auth_error(
    self: cli_main.LLMClient,
    prompt: str,
    response_model: type[object],
) -> object:
    _ = self
    _ = prompt
    _ = response_model
    raise _auth_error()
