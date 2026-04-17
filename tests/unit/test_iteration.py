# Self-written, plan v2.3 § 13.5
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest
from pydantic import BaseModel

from autosearch.core.iteration import IterationBudget, IterationController
from autosearch.core.models import Evidence, SubQuery

NOW = datetime(2026, 4, 17, 12, 0, 0)


class DummyClient:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls = 0
        self.prompts: list[str] = []

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.prompts.append(prompt)
        payload = self.payloads[self.calls]
        self.calls += 1
        return response_model.model_validate(payload)


class FakeChannel:
    name = "fake"

    def __init__(self, responses: list[list[Evidence]]) -> None:
        self.responses = list(responses)
        self.queries: list[str] = []

    async def search(self, query: SubQuery) -> list[Evidence]:
        self.queries.append(query.text)
        return self.responses.pop(0)


def make_evidence(url: str, title: str, content: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        content=content,
        source_channel="fake",
        fetched_at=NOW,
    )


async def test_iteration_run_stops_after_one_round_when_no_gaps_remain() -> None:
    controller = IterationController()
    channel = FakeChannel(
        [[make_evidence("https://example.com/one", "Pricing update", "pricing update evidence")]]
    )
    client = DummyClient([{"gaps": []}])

    result = await controller.run(
        query="pricing update",
        initial_queries=[SubQuery(text="pricing update", rationale="seed query")],
        channels=[channel],
        budget=IterationBudget(max_iterations=1, per_channel_rate_limit=0.0),
        client=client,
    )

    assert channel.queries == ["pricing update"]
    assert [evidence.url for evidence in result] == ["https://example.com/one"]
    assert result[0].score is not None
    assert client.calls == 1


async def test_iteration_run_generates_follow_up_queries_for_second_round() -> None:
    controller = IterationController()
    channel = FakeChannel(
        [
            [make_evidence("https://example.com/one", "Initial finding", "seed evidence only")],
            [make_evidence("https://example.com/two", "Follow-up finding", "limits benchmark")],
        ]
    )
    client = DummyClient(
        [
            {"gaps": [{"topic": "Latency limits", "reason": "Need a direct benchmark"}]},
            {
                "subqueries": [
                    {
                        "text": "provider latency benchmark 2026",
                        "rationale": "closes the latency gap",
                    }
                ]
            },
            {"gaps": [{"topic": "Regional coverage", "reason": "Still missing geography detail"}]},
        ]
    )

    result = await controller.run(
        query="provider latency limits",
        initial_queries=[SubQuery(text="provider latency limits", rationale="seed query")],
        channels=[channel],
        budget=IterationBudget(max_iterations=2, per_channel_rate_limit=0.0),
        client=client,
    )

    assert channel.queries == ["provider latency limits", "provider latency benchmark 2026"]
    assert {evidence.url for evidence in result} == {
        "https://example.com/one",
        "https://example.com/two",
    }
    assert len(result) == 2
    assert client.calls == 3


def test_iteration_budget_is_frozen() -> None:
    budget = IterationBudget()

    with pytest.raises(FrozenInstanceError):
        budget.max_iterations = 2
