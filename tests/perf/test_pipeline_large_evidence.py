# Self-written, plan v2.3 § 13.5
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from autosearch.core.clarify import _ClarifyCompletion
from autosearch.core.iteration import _GapReflectionResponse
from autosearch.core.models import (
    EvaluationResult,
    Evidence,
    Gap,
    GradeOutcome,
    KnowledgeRecall,
    SearchMode,
)
from autosearch.core.pipeline import Pipeline
from autosearch.core.strategy import _SubQueryBatch
from autosearch.llm.client import LLMClient
from autosearch.synthesis.outline import OutlineResponse
from autosearch.synthesis.section import _SectionWriteResponse
from tests.fixtures.fake_channel import FakeChannel

NOW = datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC)
QUERY = "querytoken framework scale check"


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
                f"Expected response model {step.response_model.__name__}, got {response_model.__name__}"
            )
        return json.dumps(step.payload)


def _make_evidence(index: int) -> Evidence:
    tokens = " ".join(
        [
            QUERY,
            f"querytoken-{index}",
            f"bucket-{index % 17}",
            f"cluster-{index % 29}",
            f"signal-{index % 37}",
        ]
    )
    return Evidence(
        url=f"https://example.com/querytoken-evidence-{index}",
        title=f"Querytoken evidence {index} {QUERY}",
        snippet=f"Synthetic snippet {index} {tokens}",
        content=(
            f"Synthetic content {index} for {QUERY}. "
            f"This evidence includes {tokens} and distinct tail marker item-{index}."
        ),
        source_channel="web",
        fetched_at=NOW,
    )


def _scripted_llm() -> LLMClient:
    provider = ScriptedProvider(
        [
            CompletionStep(
                response_model=KnowledgeRecall,
                payload=KnowledgeRecall(
                    known_facts=["The querytoken scenario needs a large-evidence scale check."],
                    gaps=[Gap(topic="Framework overhead", reason="Need end-to-end scale coverage")],
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=_ClarifyCompletion,
                payload=_ClarifyCompletion(
                    need_clarification=False,
                    question="",
                    verification="Enough information to proceed with the scale check.",
                    rubrics=[
                        "Uses the provided evidence set",
                        "Produces a cited report",
                        "Completes without clarification",
                    ],
                    mode=SearchMode.FAST,
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=_SubQueryBatch,
                payload=_SubQueryBatch(
                    subqueries=[
                        {"text": f"{QUERY} overview", "rationale": "cover overall evidence"},
                        {"text": f"{QUERY} scale", "rationale": "cover high-volume processing"},
                        {"text": f"{QUERY} citations", "rationale": "cover synthesis output"},
                    ]
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=_GapReflectionResponse,
                payload=_GapReflectionResponse(gaps=[]).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=OutlineResponse,
                payload=OutlineResponse(headings=["Overview", "Operational Notes"]).model_dump(
                    mode="json"
                ),
            ),
            CompletionStep(
                response_model=_SectionWriteResponse,
                payload=_SectionWriteResponse(
                    content=(
                        "The pipeline handles the large evidence set and still produces a "
                        "grounded report with consistent querytoken signal [1][2]."
                    ),
                    ref_ids=[1, 2],
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=_SectionWriteResponse,
                payload=_SectionWriteResponse(
                    content=(
                        "Operationally, the synthetic evidence remains attributable and the "
                        "framework overhead stays bounded for this scale check [2][3]."
                    ),
                    ref_ids=[2, 3],
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=EvaluationResult,
                payload=EvaluationResult(
                    grade=GradeOutcome.PASS,
                    follow_up_gaps=[],
                ).model_dump(mode="json"),
            ),
        ]
    )
    return LLMClient(provider_name="scripted", providers={"scripted": provider})


@pytest.mark.perf
@pytest.mark.asyncio
async def test_pipeline_handles_five_hundred_evidence_items_quickly() -> None:
    channel = FakeChannel(
        name="web",
        evidences=[_make_evidence(index) for index in range(500)],
    )
    pipeline = Pipeline(llm=_scripted_llm(), channels=[channel])

    started_at = time.perf_counter()
    result = await pipeline.run(QUERY)
    elapsed = time.perf_counter() - started_at

    assert result.delivery_status == "ok"
    assert result.markdown
    assert elapsed < 15.0
    assert channel.call_count == 3
