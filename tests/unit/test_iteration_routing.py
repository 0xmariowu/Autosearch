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


def aggregate_iteration_names(iterations: list[dict[str, object]], key: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for entry in iterations:
        values = entry.get(key)
        if not isinstance(values, list):
            continue
        for name in values:
            if not isinstance(name, str) or name in seen:
                continue
            seen.add(name)
            names.append(name)
    return names


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


async def test_routing_trace_has_iterations_list() -> None:
    controller = IterationController()
    call_order: list[str] = []
    channel = FakeChannel(
        "A",
        [
            [make_evidence("https://example.com/a-1", source_channel="A")],
            [make_evidence("https://example.com/a-2", source_channel="A")],
        ],
        call_order=call_order,
    )
    client = DummyClient(
        [
            {"gaps": [{"topic": "follow-up", "reason": "Need one more pass"}]},
            {"subqueries": [{"text": "follow-up query", "rationale": "continue research"}]},
            {"gaps": []},
        ]
    )

    await controller.run(
        query="routing trace history",
        initial_queries=[SubQuery(text="routing trace history", rationale="seed")],
        channels=[channel],
        budget=IterationBudget(max_iterations=2, per_channel_rate_limit=0.0),
        client=client,
    )

    iterations = controller.routing_trace["iterations"]

    assert len(iterations) == 2
    assert [entry["iteration"] for entry in iterations] == [1, 2]


async def test_iterations_entry_shape() -> None:
    controller = IterationController()
    channel = FakeChannel(
        "A",
        [[make_evidence("https://example.com/a", source_channel="A")]],
        call_order=[],
    )
    client = DummyClient([{"gaps": []}])

    await controller.run(
        query="routing trace shape",
        initial_queries=[SubQuery(text="routing trace shape", rationale="seed")],
        channels=[channel],
        budget=IterationBudget(max_iterations=1, per_channel_rate_limit=0.0),
        client=client,
    )

    iteration_trace = controller.routing_trace["iterations"][0]

    assert set(iteration_trace) == {
        "iteration",
        "priority_ran",
        "rest_ran",
        "skipped",
        "priority_evidence_count",
        "fallback_triggered",
        "batch_count",
    }
    assert iteration_trace["batch_count"] == 1


async def test_iterations_priority_ran_matches_actual_channels_this_iteration() -> None:
    controller = IterationController()
    call_order: list[str] = []
    channels = [
        FakeChannel(
            "arxiv",
            [
                [
                    make_evidence(f"https://example.com/arxiv-{index}", source_channel="arxiv")
                    for index in range(FALLBACK_THRESHOLD)
                ],
                [],
            ],
            call_order=call_order,
        ),
        FakeChannel(
            "devto",
            [[make_evidence("https://example.com/devto-2", source_channel="devto")]],
            call_order=call_order,
        ),
    ]
    client = DummyClient(
        [
            {"gaps": [{"topic": "follow-up", "reason": "Need another pass"}]},
            {"subqueries": [{"text": "follow-up query", "rationale": "continue research"}]},
            {"gaps": []},
        ]
    )

    await controller.run(
        query="routing tiers",
        initial_queries=[SubQuery(text="routing tiers", rationale="seed")],
        channels=channels,
        budget=IterationBudget(max_iterations=2, per_channel_rate_limit=0.0),
        client=client,
        priority_channels={"arxiv"},
    )

    iterations = controller.routing_trace["iterations"]

    assert call_order == ["arxiv", "arxiv", "devto"]
    assert iterations[0]["priority_ran"] == ["arxiv"]
    assert iterations[0]["rest_ran"] == []
    assert iterations[1]["priority_ran"] == ["arxiv"]
    assert iterations[1]["rest_ran"] == ["devto"]
    assert iterations[0]["priority_evidence_count"] == FALLBACK_THRESHOLD
    assert iterations[1]["priority_evidence_count"] == 0


async def test_iterations_preserves_aggregate_view() -> None:
    controller = IterationController()
    call_order: list[str] = []
    channels = [
        FakeChannel(
            "arxiv",
            [
                [
                    make_evidence(f"https://example.com/arxiv-{index}", source_channel="arxiv")
                    for index in range(FALLBACK_THRESHOLD)
                ],
                [],
            ],
            call_order=call_order,
        ),
        FakeChannel(
            "devto",
            [[make_evidence("https://example.com/devto-2", source_channel="devto")]],
            call_order=call_order,
        ),
        FakeChannel("bilibili", [], call_order=call_order),
    ]
    client = DummyClient(
        [
            {"gaps": [{"topic": "follow-up", "reason": "Need another pass"}]},
            {"subqueries": [{"text": "follow-up query", "rationale": "continue research"}]},
            {"gaps": []},
        ]
    )

    await controller.run(
        query="aggregate routing trace",
        initial_queries=[SubQuery(text="aggregate routing trace", rationale="seed")],
        channels=channels,
        budget=IterationBudget(max_iterations=2, per_channel_rate_limit=0.0),
        client=client,
        priority_channels={"arxiv"},
        skip_channels={"bilibili"},
    )

    iterations = controller.routing_trace["iterations"]

    assert controller.routing_trace["priority_ran"] == aggregate_iteration_names(
        iterations, "priority_ran"
    )
    assert controller.routing_trace["rest_ran"] == aggregate_iteration_names(iterations, "rest_ran")
    assert controller.routing_trace["skipped_channels"] == aggregate_iteration_names(
        iterations, "skipped"
    )


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

    evidences, _ = await controller.run(
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


async def test_iterations_fallback_triggered_per_iteration() -> None:
    controller = IterationController()
    call_order: list[str] = []
    channels = [
        FakeChannel(
            "arxiv",
            [
                [],
                [
                    make_evidence(f"https://example.com/arxiv-{index}", source_channel="arxiv")
                    for index in range(FALLBACK_THRESHOLD)
                ],
            ],
            call_order=call_order,
        ),
        FakeChannel(
            "devto",
            [[make_evidence("https://example.com/devto-1", source_channel="devto")]],
            call_order=call_order,
        ),
    ]
    client = DummyClient(
        [
            {"gaps": [{"topic": "follow-up", "reason": "Need another pass"}]},
            {"subqueries": [{"text": "follow-up query", "rationale": "continue research"}]},
            {"gaps": []},
        ]
    )

    await controller.run(
        query="iteration fallback trace",
        initial_queries=[SubQuery(text="iteration fallback trace", rationale="seed")],
        channels=channels,
        budget=IterationBudget(max_iterations=2, per_channel_rate_limit=0.0),
        client=client,
        priority_channels={"arxiv"},
    )

    iterations = controller.routing_trace["iterations"]

    assert call_order == ["arxiv", "devto", "arxiv"]
    assert iterations[0]["fallback_triggered"] is True
    assert iterations[1]["fallback_triggered"] is False
    assert controller.routing_trace["fallback_triggered"] is True


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

    evidences, _ = await controller.run(
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


async def test_iterations_empty_when_no_iterations_run() -> None:
    controller = IterationController()
    channel = FakeChannel(
        "A",
        [[make_evidence("https://example.com/a", source_channel="A")]],
        call_order=[],
    )
    client = DummyClient([])

    evidences, research_trace = await controller.run(
        query="zero budget",
        initial_queries=[SubQuery(text="zero budget", rationale="seed")],
        channels=[channel],
        budget=IterationBudget(max_iterations=0, per_channel_rate_limit=0.0),
        client=client,
    )

    assert evidences == []
    assert research_trace == []
    assert controller.routing_trace["iterations"] == []


async def test_backward_compat_aggregate_fields_unchanged() -> None:
    controller = IterationController()
    call_order: list[str] = []
    channels = [
        FakeChannel("A", [[]], call_order=call_order),
        FakeChannel(
            "B",
            [[make_evidence("https://example.com/b", source_channel="B")]],
            call_order=call_order,
        ),
        FakeChannel("C", [], call_order=call_order),
    ]
    client = DummyClient([{"gaps": []}])

    evidences, _ = await controller.run(
        query="backward compat routing trace",
        initial_queries=[SubQuery(text="backward compat routing trace", rationale="seed")],
        channels=channels,
        budget=IterationBudget(max_iterations=1, per_channel_rate_limit=0.0),
        client=client,
        priority_channels={"A"},
        skip_channels={"C"},
    )

    assert [evidence.source_channel for evidence in evidences] == ["B"]
    assert call_order == ["A", "B"]
    assert controller.routing_trace["priority"] == ["A"]
    assert controller.routing_trace["skip"] == ["C"]
    assert controller.routing_trace["priority_ran"] == ["A"]
    assert controller.routing_trace["rest_ran"] == ["B"]
    assert controller.routing_trace["skipped_channels"] == ["C"]
    assert controller.routing_trace["priority_evidence_count"] == 0
    assert controller.routing_trace["fallback_triggered"] is True
