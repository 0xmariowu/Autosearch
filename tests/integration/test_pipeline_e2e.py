# Self-written, plan v2.3 § 13.5
import json
from dataclasses import dataclass
from datetime import datetime

import pytest
from pydantic import BaseModel

from autosearch.core.clarify import _ClarifyCompletion
from autosearch.core.iteration import _GapReflectionResponse
from autosearch.core.models import EvaluationResult, Gap, GradeOutcome, KnowledgeRecall, SearchMode
from autosearch.core.pipeline import Pipeline
from autosearch.core.strategy import _SubQueryBatch
from autosearch.llm.client import LLMClient
from autosearch.synthesis.outline import OutlineResponse
from autosearch.synthesis.section import _SectionWriteResponse
from tests.fixtures.fake_channel import FakeChannel

# These internal response models are imported on purpose so the scripted provider can assert that
# Pipeline is exercising the existing module contracts instead of bypassing them in tests.

NOW = datetime(2026, 4, 17, 12, 0, 0)


@dataclass(frozen=True)
class CompletionStep:
    response_model: type[BaseModel]
    payload: dict[str, object]


class ScriptedProvider:
    name = "scripted"

    def __init__(self, steps: list[CompletionStep]) -> None:
        self.steps = list(steps)
        self.calls = 0
        self.prompts: list[str] = []
        self.response_models: list[type[BaseModel]] = []

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        self.prompts.append(prompt)
        self.response_models.append(response_model)
        if self.calls >= len(self.steps):
            raise AssertionError(
                f"Unexpected extra LLM call for {response_model.__name__}: {prompt[:120]!r}"
            )

        step = self.steps[self.calls]
        self.calls += 1
        if response_model is not step.response_model:
            raise AssertionError(
                "Expected response model "
                f"{step.response_model.__name__}, got {response_model.__name__}"
            )
        return json.dumps(step.payload)


def make_evidence(url: str, title: str, source_channel: str, body: str) -> BaseModel:
    from autosearch.core.models import Evidence

    return Evidence(
        url=url,
        title=title,
        snippet=body[:80],
        content=body,
        source_channel=source_channel,
        fetched_at=NOW,
    )


@pytest.mark.asyncio
async def test_pipeline_run_produces_report_and_quality_pass() -> None:
    provider = ScriptedProvider(
        [
            CompletionStep(
                response_model=KnowledgeRecall,
                payload=KnowledgeRecall(
                    known_facts=["BM25 is a lexical ranking method."],
                    gaps=[Gap(topic="Current benchmarks", reason="Need fresh comparisons")],
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=_ClarifyCompletion,
                payload=_ClarifyCompletion(
                    need_clarification=False,
                    question="",
                    verification="I have enough information to research the current tradeoffs.",
                    rubrics=[
                        "Includes recent evidence",
                        "Compares the sources directly",
                        "Provides cited conclusions",
                    ],
                    mode=SearchMode.FAST,
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=_SubQueryBatch,
                payload=_SubQueryBatch(
                    subqueries=[
                        {
                            "text": "bm25 ranking benchmarks 2026",
                            "rationale": "covers current benchmark evidence",
                        },
                        {
                            "text": "bm25 retrieval tradeoffs comparison",
                            "rationale": "covers direct tradeoff analysis",
                        },
                        {
                            "text": "bm25 relevance evaluation sources",
                            "rationale": "covers cited conclusions",
                        },
                    ]
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=_GapReflectionResponse,
                payload=_GapReflectionResponse(gaps=[]).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=OutlineResponse,
                payload=OutlineResponse(headings=["Overview", "Practical Takeaways"]).model_dump(
                    mode="json"
                ),
            ),
            CompletionStep(
                response_model=_SectionWriteResponse,
                payload=_SectionWriteResponse(
                    content=(
                        "BM25 remains competitive for lexical retrieval and is easy to reason "
                        "about in ranking pipelines [1][2]."
                    ),
                    ref_ids=[1, 2],
                ).model_dump(mode="json"),
            ),
            CompletionStep(
                response_model=_SectionWriteResponse,
                payload=_SectionWriteResponse(
                    content=(
                        "Operationally, the strongest signal here is straightforward deployment "
                        "and transparent scoring behavior backed by multiple sources [2][3]."
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
    llm = LLMClient(provider_name="scripted", providers={"scripted": provider})
    channel = FakeChannel(
        name="web",
        evidences=[
            make_evidence(
                "https://example.com/benchmarks",
                "BM25 benchmark summary",
                "web",
                "A benchmark summary comparing BM25 to related ranking approaches.",
            ),
            make_evidence(
                "https://example.com/tradeoffs",
                "BM25 tradeoffs",
                "web",
                "Tradeoffs between BM25 and adjacent retrieval strategies in production.",
            ),
            make_evidence(
                "https://example.com/deployment",
                "Deploying BM25 systems",
                "web",
                "Practical deployment notes and transparent scoring details for BM25.",
            ),
            make_evidence(
                "https://example.com/citations",
                "Evidence-backed BM25 conclusions",
                "web",
                "A cited write-up that summarizes the most important BM25 conclusions.",
            ),
        ],
    )

    result = await Pipeline(llm=llm, channels=[channel]).run(
        "Should I still use BM25 for lexical search?",
    )

    assert result.status == "ok"
    assert result.markdown is not None
    assert "## References" in result.markdown
    assert "## Sources" in result.markdown
    assert "## Overview" in result.markdown
    assert result.evidences
    assert result.quality is not None
    assert result.quality.grade is GradeOutcome.PASS
    assert channel.call_count >= 1
    assert provider.calls == len(provider.steps)
