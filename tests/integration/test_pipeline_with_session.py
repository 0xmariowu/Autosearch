# Self-written, plan v2.3 § 11
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from autosearch.core.clarify import _ClarifyCompletion
from autosearch.core.iteration import _GapReflectionResponse
from autosearch.core.models import EvaluationResult, Gap, GradeOutcome, KnowledgeRecall, SearchMode
from autosearch.core.pipeline import Pipeline
from autosearch.core.strategy import _SubQueryBatch
from autosearch.llm.client import LLMClient
from autosearch.observability.cost import CostTracker
from autosearch.persistence.session_store import SessionStore
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
        if self.calls >= len(self.steps):
            raise AssertionError(f"Unexpected extra LLM call for {response_model.__name__}")

        step = self.steps[self.calls]
        self.calls += 1
        if response_model is not step.response_model:
            raise AssertionError(
                f"Expected {step.response_model.__name__}, got {response_model.__name__}"
            )
        return json.dumps(step.payload)


def _make_evidence(url: str, title: str, body: str) -> BaseModel:
    from autosearch.core.models import Evidence

    return Evidence(
        url=url,
        title=title,
        snippet=body[:80],
        content=body,
        source_channel="web",
        fetched_at=NOW,
        score=0.9,
    )


@pytest.mark.asyncio
async def test_pipeline_run_records_session_queries_evidence_and_cost() -> None:
    store = await SessionStore.open(":memory:")
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
    tracker = CostTracker()
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

    try:
        result = await Pipeline(
            llm=llm,
            channels=[channel],
            cost_tracker=tracker,
            session_store=store,
        ).run("Should I still use BM25 for lexical search?")
        session = await store.fetch_session(result.session_id or "")
    finally:
        await store.close()

    assert result.session_id is not None
    assert re.fullmatch(r"[0-9a-f]{12}", result.session_id)
    assert result.cost > 0.0
    assert session is not None
    assert session["id"] == result.session_id
    assert session["markdown"]
    assert session["finished_at"] is not None
    assert session["cost"] == pytest.approx(result.cost)
    assert session["evidence"]
    assert session["query_log"]
