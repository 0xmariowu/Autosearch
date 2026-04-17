# Self-written, plan v2.3 § 13.5
import pytest

import autosearch.llm.client as client_module


def test_llm_client_raises_helpful_error_when_no_provider_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env_var in (
        "AUTOSEARCH_LLM_MODE",
        "AUTOSEARCH_LLM_PROVIDER",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(
        client_module.ClaudeCodeProvider,
        "is_available",
        staticmethod(lambda: False),
    )

    with pytest.raises(RuntimeError, match="No LLM provider configured") as exc_info:
        client_module.LLMClient()

    message = str(exc_info.value)
    assert "ANTHROPIC_API_KEY" in message
    assert "OPENAI_API_KEY" in message
    assert "GOOGLE_API_KEY" in message
    assert "claude" in message
