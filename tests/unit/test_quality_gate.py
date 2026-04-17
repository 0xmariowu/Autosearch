# Self-written, plan v2.3 § 13.5
from datetime import datetime

from pydantic import BaseModel

from autosearch.core.models import (
    EvaluationResult,
    Evidence,
    Gap,
    GradeOutcome,
    Rubric,
    Section,
)
from autosearch.quality.gate import QualityGate


class DummyClient:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls = 0
        self.prompts: list[str] = []
        self.response_models: list[type[BaseModel]] = []

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.prompts.append(prompt)
        self.response_models.append(response_model)
        payload = self.payloads[self.calls]
        self.calls += 1
        return response_model.model_validate(payload)


def make_section() -> Section:
    return Section(
        heading="Provider comparison",
        content="Provider A has better relevance coverage with fresher pricing notes.",
        ref_ids=[1],
    )


def make_rubrics() -> list[Rubric]:
    return [
        Rubric(text="Compares named providers", weight=1.0),
        Rubric(text="Includes current pricing evidence", weight=1.5),
    ]


def make_evidences() -> list[Evidence]:
    return [
        Evidence(
            url="https://example.com/pricing",
            title="Provider pricing",
            content="Provider A starts at $10 and Provider B starts at $15.",
            source_channel="web",
            fetched_at=datetime(2026, 4, 17, 12, 0, 0),
        )
    ]


async def test_quality_gate_returns_pass_result_when_llm_passes() -> None:
    client = DummyClient([{"grade": "pass", "follow_up_gaps": []}])

    result = await QualityGate().evaluate(make_section(), make_rubrics(), make_evidences(), client)

    assert result == EvaluationResult(grade=GradeOutcome.PASS, follow_up_gaps=[])


async def test_quality_gate_returns_fail_result_with_follow_up_gaps() -> None:
    client = DummyClient(
        [
            {
                "grade": "fail",
                "follow_up_gaps": [
                    {"topic": "Provider C pricing", "reason": "Current pricing is missing"},
                    {"topic": "Latency comparison", "reason": "No direct benchmark evidence"},
                ],
            }
        ]
    )

    result = await QualityGate().evaluate(make_section(), make_rubrics(), make_evidences(), client)

    assert result.grade is GradeOutcome.FAIL
    assert result.follow_up_gaps == [
        Gap(topic="Provider C pricing", reason="Current pricing is missing"),
        Gap(topic="Latency comparison", reason="No direct benchmark evidence"),
    ]


async def test_quality_gate_feeds_section_and_rubrics_into_prompt() -> None:
    client = DummyClient([{"grade": "pass", "follow_up_gaps": []}])
    section = make_section()
    rubrics = make_rubrics()

    await QualityGate().evaluate(section, rubrics, make_evidences(), client)

    prompt = client.prompts[0]
    assert section.heading in prompt
    assert section.content in prompt
    assert "Compares named providers" in prompt
    assert "Includes current pricing evidence" in prompt
