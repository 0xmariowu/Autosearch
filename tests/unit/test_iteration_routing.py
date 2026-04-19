# Self-written, plan 0420 W5 F501 routing
from datetime import datetime

from pydantic import BaseModel

from autosearch.core.iteration import FALLBACK_THRESHOLD, IterationBudget, IterationController
from autosearch.core.models import Evidence, SubQuery

NOW = datetime(2026, 4, 20, 12, 0, 0)


class DummyClient:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls = 0

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        _ = prompt
        payload = self.payloads[self.calls]
        self.calls += 1
        return response_model.model_validate(payload)


class FakeChannel:
    languages = ["en"]

    def __init__(
        self,
        name: str,
        responses: list[list[Evidence]],
        *,
        call_order: list[str],
    ) -> None:
        self.name = name
        self.responses = list(responses)
        self.queries: list[str] = []
        self.call_order = call_order

    async def search(self, query: SubQuery) -> list[Evidence]:
        self.queries.append(query.text)
        self.call_order.append(self.name)
        return self.responses.pop(0)


def make_evidence(url: str, *, source_channel: str) -> Evidence:
    return Evidence(
        url=url,
        title=url.rsplit("/", maxsplit=1)[-1],
        content="evidence",
        source_channel=source_channel,
        fetched_at=NOW,
    )


async def test_iteration_runs_priority_channels_first() -> None:
    controller = IterationController()
    call_order: list[str] = []
    subqueries = [SubQuery(text="fastapi dependency override", rationale="seed")]
    channels = [
        FakeChannel(
            "A",
            [[make_evidence("https://example.com/a", source_channel="A")]],
            call_order=call_order,
        ),
        FakeChannel(
            "B",
            [[make_evidence("https://example.com/b", source_channel="B")]],
            call_order=call_order,
        ),
        FakeChannel(
            "C",
            [[make_evidence("https://example.com/c", source_channel="C")]],
            call_order=call_order,
        ),
    ]

    await controller._search(subqueries, channels, 1, priority_channels={"A"})

    assert call_order[0] == "A"
    assert set(call_order[1:]) == {"B", "C"}
    assert controller.routing_trace["priority_ran"] == ["A"]
    assert controller.routing_trace["rest_ran"] == ["B", "C"]


async def test_iteration_skips_channels_in_skip_list() -> None:
    controller = IterationController()
    call_order: list[str] = []
    subqueries = [SubQuery(text="search ranking", rationale="seed")]
    channels = [
        FakeChannel(
            "A",
            [[make_evidence("https://example.com/a", source_channel="A")]],
            call_order=call_order,
        ),
        FakeChannel(
            "B",
            [[make_evidence("https://example.com/b", source_channel="B")]],
            call_order=call_order,
        ),
    ]

    await controller._search(subqueries, channels, 1, skip_channels={"B"})

    assert call_order == ["A"]
    assert channels[1].queries == []
    assert controller.routing_trace["skipped_channels"] == ["B"]


async def test_iteration_fallback_triggered_when_priority_empty() -> None:
    controller = IterationController()
    call_order: list[str] = []
    channels = [
        FakeChannel("A", [[]], call_order=call_order),
        FakeChannel(
            "B",
            [[make_evidence("https://example.com/b", source_channel="B")]],
            call_order=call_order,
        ),
    ]
    client = DummyClient([{"gaps": []}])

    evidences = await controller.run(
        query="empty priority evidence",
        initial_queries=[SubQuery(text="empty priority evidence", rationale="seed")],
        channels=channels,
        budget=IterationBudget(max_iterations=1, per_channel_rate_limit=0.0),
        client=client,
        priority_channels={"A"},
    )

    assert [evidence.source_channel for evidence in evidences] == ["B"]
    assert call_order == ["A", "B"]
    assert controller.routing_trace["priority_evidence_count"] == 0
    assert controller.routing_trace["fallback_triggered"] is True
    assert controller.routing_trace["rest_ran"] == ["B"]


async def test_iteration_fallback_not_triggered_when_priority_sufficient() -> None:
    controller = IterationController()
    call_order: list[str] = []
    channels = [
        FakeChannel(
            "A",
            [
                [
                    make_evidence(f"https://example.com/a-{index}", source_channel="A")
                    for index in range(FALLBACK_THRESHOLD)
                ]
            ],
            call_order=call_order,
        ),
        FakeChannel(
            "B",
            [[make_evidence("https://example.com/b", source_channel="B")]],
            call_order=call_order,
        ),
    ]
    client = DummyClient([{"gaps": []}])

    evidences = await controller.run(
        query="sufficient priority evidence",
        initial_queries=[SubQuery(text="sufficient priority evidence", rationale="seed")],
        channels=channels,
        budget=IterationBudget(max_iterations=1, per_channel_rate_limit=0.0),
        client=client,
        priority_channels={"A"},
    )

    assert len(evidences) == FALLBACK_THRESHOLD
    assert call_order == ["A"]
    assert channels[1].queries == []
    assert controller.routing_trace["priority_evidence_count"] == FALLBACK_THRESHOLD
    assert controller.routing_trace["fallback_triggered"] is False
    assert controller.routing_trace["rest_ran"] == []
