# Self-written, plan 0420 W4 F402
from pydantic import BaseModel

import autosearch.core.iteration as iteration_module
from autosearch.core.iteration import generate_perspectives


class FakeLLMClient:
    def __init__(self, payload: dict[str, object] | Exception) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.prompts.append(prompt)
        if isinstance(self.payload, Exception):
            raise self.payload
        return response_model.model_validate(self.payload)


class RecordingLogger:
    def __init__(self) -> None:
        self.warning_calls: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.warning_calls.append((event, kwargs))


async def test_generate_perspectives_returns_requested_count() -> None:
    client = FakeLLMClient(
        {
            "labels": [
                "economic feasibility",
                "environmental impact",
                "policy implementation",
            ]
        }
    )

    labels = await generate_perspectives(
        "renewable energy adoption",
        client,
        num_perspectives=3,
    )

    assert labels == [
        "economic feasibility",
        "environmental impact",
        "policy implementation",
    ]


async def test_generate_perspectives_llm_error_fallback() -> None:
    client = FakeLLMClient(RuntimeError("llm unavailable"))

    labels = await generate_perspectives(
        "renewable energy adoption",
        client,
        num_perspectives=3,
    )

    assert labels == ["default"]


async def test_generate_perspectives_empty_response_fallback() -> None:
    client = FakeLLMClient({"labels": []})

    labels = await generate_perspectives(
        "renewable energy adoption",
        client,
        num_perspectives=3,
    )

    assert labels == ["default"]


async def test_generate_perspectives_labels_are_short() -> None:
    client = FakeLLMClient(
        {
            "labels": [
                "economic feasibility",
                "this label is intentionally much longer than sixty characters to validate filtering",
                "environmental impact",
                "policy implementation",
            ]
        }
    )

    labels = await generate_perspectives(
        "renewable energy adoption",
        client,
        num_perspectives=3,
    )

    assert labels == [
        "economic feasibility",
        "environmental impact",
        "policy implementation",
    ]
    assert all(len(label) <= 60 for label in labels)


async def test_generate_perspectives_clamp_above_3_emits_warning(monkeypatch) -> None:
    client = FakeLLMClient(
        {
            "labels": [
                "economic feasibility",
                "environmental impact",
                "policy implementation",
                "supply chain resilience",
                "consumer adoption",
            ]
        }
    )
    recording_logger = RecordingLogger()
    monkeypatch.setattr(iteration_module, "logger", recording_logger)

    labels = await generate_perspectives(
        "renewable energy adoption",
        client,
        num_perspectives=5,
    )

    assert labels == [
        "economic feasibility",
        "environmental impact",
        "policy implementation",
    ]
    assert recording_logger.warning_calls == [
        (
            "num_perspectives_clamped",
            {
                "requested": 5,
                "actual": 3,
            },
        )
    ]
