# Self-written, plan 0420 W4 F402
from pydantic import BaseModel

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
