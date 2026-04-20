# Self-written, plan v2.3 § token fidelity
import json
from dataclasses import dataclass
from datetime import UTC, datetime

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
from autosearch.observability.cost import CostTracker
from autosearch.synthesis.outline import OutlineResponse
from autosearch.synthesis.section import _SectionWriteResponse
from tests.fixtures.fake_channel import FakeChannel

NOW = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CompletionStep:
    response_model: type[BaseModel]
    payload: dict[str, object]


class ScriptedProvider:
    name = "scripted"
    model = "gpt-4o"

    def __init__(self, steps: list[CompletionStep]) -> None:
        self.steps = list(steps)
        self.calls = 0

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> str:
        _ = prompt
        step = self.steps[self.calls]
        self.calls += 1
        if response_model is not step.response_model:
            raise AssertionError(
                f"Expected {step.response_model.__name__}, got {response_model.__name__}"
            )
        return json.dumps(step.payload)


def _make_evidence(url: str, title: str, body: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet=body[:80],
        content=body,
        source_channel="web",
        fetched_at=NOW,
        score=0.9,
    )


async def test_pipeline_populates_token_counts_from_cost_tracker_breakdown() -> None:
    tracker = CostTracker()
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
                    verification="Enough information to proceed.",
                    rubrics=[
                        "Includes current evidence",
                        "Compares sources directly",
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
                        "Operationally, transparent scoring and straightforward deployment "
                        "remain the strongest reasons to use BM25 [2][3]."
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
            _make_evidence(
                "https://example.com/benchmarks",
                "BM25 benchmark summary",
                "A benchmark summary comparing BM25 to related ranking approaches.",
            ),
            _make_evidence(
                "https://example.com/tradeoffs",
                "BM25 tradeoffs",
                "Tradeoffs between BM25 and adjacent retrieval strategies in production.",
            ),
        ],
    )

    result = await Pipeline(
        llm=llm,
        channels=[channel],
        cost_tracker=tracker,
    ).run("Should I still use BM25 for lexical search?")

    breakdown = tracker.breakdown()
    expected_prompt_tokens = sum(int(values["input_tokens"]) for values in breakdown.values())
    expected_completion_tokens = sum(int(values["output_tokens"]) for values in breakdown.values())

    assert result.prompt_tokens == expected_prompt_tokens
    assert result.completion_tokens == expected_completion_tokens
    assert result.prompt_tokens > 0
    assert result.completion_tokens > 0
