# Self-written, plan v2.3 § 13.5
import json
from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from autosearch.core.clarify import _ClarifyCompletion
from autosearch.core.models import Gap, KnowledgeRecall, SearchMode
from autosearch.core.pipeline import Pipeline
from autosearch.llm.client import LLMClient
from tests.fixtures.fake_channel import FakeChannel

# These internal response models are imported on purpose so the scripted provider can assert that
# Pipeline is using the existing clarify module contract for the early-exit branch.


@dataclass(frozen=True)
class CompletionStep:
    response_model: type[BaseModel]
    payload: dict[str, object]


class ScriptedProvider:
    name = "scripted"

    def __init__(self, steps: list[CompletionStep]) -> None:
        self.steps = list(steps)
        self.calls = 0

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        _ = prompt
        if self.calls >= len(self.steps):
            raise AssertionError(f"Unexpected extra LLM call for {response_model.__name__}")
        step = self.steps[self.calls]
        self.calls += 1
        if response_model is not step.response_model:
            raise AssertionError(
                "Expected response model "
                f"{step.response_model.__name__}, got {response_model.__name__}"
            )
        return json.dumps(step.payload)


@pytest.mark.asyncio
async def test_pipeline_exits_early_when_clarification_is_required() -> None:
    provider = ScriptedProvider(
        [
            CompletionStep(
                response_model=KnowledgeRecall,
                payload=KnowledgeRecall(
                    known_facts=[],
                    gaps=[Gap(topic="Target audience", reason="Needed to scope the report")],
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=_ClarifyCompletion,
                payload=_ClarifyCompletion(
                    need_clarification=True,
                    question="Do you want an engineering comparison or a buyer guide?",
                    verification="",
                    rubrics=[
                        "States the audience explicitly",
                        "Names the comparison target",
                        "Explains the selection criteria",
                    ],
                    mode=SearchMode.DEEP,
                ).model_dump(mode="json"),
            ),
        ]
    )
    llm = LLMClient(provider_name="scripted", providers={"scripted": provider})
    channel = FakeChannel(name="web", evidences=[])

    result = await Pipeline(llm=llm, channels=[channel]).run("best search tool")

    assert result.delivery_status == "needs_clarification"
    assert result.markdown is None
    assert result.evidences == []
    assert result.quality is None
    assert result.iterations == 0
    assert result.clarification.need_clarification is True
    assert channel.call_count == 0
    assert provider.calls == len(provider.steps)
