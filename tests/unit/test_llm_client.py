# Self-written, plan v2.3 § 6
import pytest
from pydantic import BaseModel, ValidationError

import autosearch.llm.client as client_module


class DemoResponse(BaseModel):
    answer: str


class DummyProvider:
    name = "dummy"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        _ = prompt
        _ = response_model
        response = self.responses[self.calls]
        self.calls += 1
        return response


@pytest.mark.parametrize(
    ("env_var", "provider_attr", "expected_name"),
    [
        ("ANTHROPIC_API_KEY", "AnthropicProvider", "anthropic"),
        ("OPENAI_API_KEY", "OpenAIProvider", "openai"),
        ("GOOGLE_API_KEY", "GeminiProvider", "gemini"),
    ],
)
def test_llm_client_selects_provider_from_env(
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    provider_attr: str,
    expected_name: str,
) -> None:
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(env_var, "test-key")
    monkeypatch.setattr(
        client_module.ClaudeCodeProvider, "is_available", staticmethod(lambda: False)
    )

    class FakeProvider:
        name = expected_name

        async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
            _ = prompt
            _ = response_model
            return '{"answer":"ok"}'

    monkeypatch.setattr(client_module, provider_attr, FakeProvider)

    client = client_module.LLMClient()

    assert client.provider_name == expected_name
    assert list(client.providers) == [expected_name]


async def test_llm_client_retries_on_json_parse_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = DummyProvider(["not-json", '{"answer":"ok"}'])
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)
    client = client_module.LLMClient(
        provider_name="dummy",
        providers={"dummy": provider},
        retry_backoff_seconds=0.1,
    )

    result = await client.complete("test prompt", DemoResponse)

    assert result.answer == "ok"
    assert provider.calls == 2
    assert sleeps == [0.1]


async def test_llm_client_raises_validation_error_on_schema_mismatch() -> None:
    provider = DummyProvider(['{"wrong":"shape"}'])
    client = client_module.LLMClient(provider_name="dummy", providers={"dummy": provider})

    with pytest.raises(ValidationError):
        await client.complete("test prompt", DemoResponse)

    assert provider.calls == 1
