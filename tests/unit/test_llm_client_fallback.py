import pytest
import httpx
from pydantic import BaseModel

import autosearch.llm.client as client_module
from autosearch.observability.cost import CostTracker


class DemoResponse(BaseModel):
    answer: str


class ScriptedProvider:
    def __init__(self, name: str, model: str, steps: list[str | Exception]) -> None:
        self.name = name
        self.model = model
        self.steps = list(steps)
        self.calls = 0

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        _ = prompt
        _ = response_model
        step = self.steps[self.calls]
        self.calls += 1
        if isinstance(step, Exception):
            raise step
        return step


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.com/llm")
    response = httpx.Response(status_code=status_code, request=request)
    return httpx.HTTPStatusError(
        f"{status_code} response",
        request=request,
        response=response,
    )


async def test_llm_client_falls_back_on_http_500_and_tracks_provider_cost() -> None:
    primary = ScriptedProvider("primary", "primary-model", [_status_error(500)])
    secondary = ScriptedProvider("secondary", "secondary-model", ['{"answer":"ok"}'])
    tracker = CostTracker()
    client = client_module.LLMClient(
        provider_name="primary",
        provider_chain=["primary", "secondary"],
        providers={"primary": primary, "secondary": secondary},
        cost_tracker=tracker,
    )

    result = await client.complete("test prompt", DemoResponse)

    breakdown = tracker.breakdown()
    assert result.answer == "ok"
    assert primary.calls == 1
    assert secondary.calls == 1
    assert client.provider_name == "secondary"
    assert client.fallback_count == 1
    assert "primary-model" not in breakdown
    assert breakdown["secondary-model"]["notes"] == ["served_by_provider=secondary"]


async def test_llm_client_falls_back_on_timeout_exception() -> None:
    primary = ScriptedProvider("primary", "primary-model", [httpx.TimeoutException("timed out")])
    secondary = ScriptedProvider("secondary", "secondary-model", ['{"answer":"ok"}'])
    client = client_module.LLMClient(
        provider_name="primary",
        provider_chain=["primary", "secondary"],
        providers={"primary": primary, "secondary": secondary},
    )

    result = await client.complete("test prompt", DemoResponse)

    assert result.answer == "ok"
    assert primary.calls == 1
    assert secondary.calls == 1
    assert client.fallback_count == 1


async def test_llm_client_does_not_fallback_on_http_400() -> None:
    primary = ScriptedProvider("primary", "primary-model", [_status_error(400)])
    secondary = ScriptedProvider("secondary", "secondary-model", ['{"answer":"ok"}'])
    client = client_module.LLMClient(
        provider_name="primary",
        provider_chain=["primary", "secondary"],
        providers={"primary": primary, "secondary": secondary},
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.complete("test prompt", DemoResponse)

    assert primary.calls == 1
    assert secondary.calls == 0
    assert client.fallback_count == 0


async def test_llm_client_keeps_json_parse_retries_on_same_provider() -> None:
    primary = ScriptedProvider("primary", "primary-model", ["not-json", '{"answer":"ok"}'])
    secondary = ScriptedProvider("secondary", "secondary-model", ['{"answer":"unused"}'])
    client = client_module.LLMClient(
        provider_name="primary",
        provider_chain=["primary", "secondary"],
        providers={"primary": primary, "secondary": secondary},
        retry_backoff_seconds=0.0,
    )

    result = await client.complete("test prompt", DemoResponse)

    assert result.answer == "ok"
    assert primary.calls == 2
    assert secondary.calls == 0
    assert client.fallback_count == 0


async def test_llm_client_raises_all_providers_failed_error_when_chain_exhausted() -> None:
    primary = ScriptedProvider("primary", "primary-model", [httpx.TimeoutException("primary down")])
    secondary = ScriptedProvider("secondary", "secondary-model", [_status_error(503)])
    client = client_module.LLMClient(
        provider_name="primary",
        provider_chain=["primary", "secondary"],
        providers={"primary": primary, "secondary": secondary},
    )

    with pytest.raises(client_module.AllProvidersFailedError) as exc_info:
        await client.complete("test prompt", DemoResponse)

    error = exc_info.value
    assert list(error.provider_errors) == ["primary", "secondary"]
    assert isinstance(error.provider_errors["primary"], httpx.TimeoutException)
    assert isinstance(error.provider_errors["secondary"], httpx.HTTPStatusError)
    assert "primary" in str(error)
    assert "secondary" in str(error)


def test_llm_client_respects_auto_provider_chain_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOSEARCH_PROVIDER_CHAIN", "secondary, primary")
    client = client_module.LLMClient(
        providers={
            "primary": ScriptedProvider("primary", "primary-model", ['{"answer":"ok"}']),
            "secondary": ScriptedProvider("secondary", "secondary-model", ['{"answer":"ok"}']),
        }
    )

    assert client.provider_chain == ["secondary", "primary"]
    assert client.provider_name == "secondary"
