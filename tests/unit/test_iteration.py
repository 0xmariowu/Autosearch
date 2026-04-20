# Self-written, plan v2.3 § 13.5
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from autosearch.core import context_compaction as context_compaction_module
from autosearch.core.iteration import IterationBudget, IterationController
from autosearch.core.models import Evidence, EvidenceDigest, Gap, SubQuery
from autosearch.persistence.session_store import SessionStore

NOW = datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC)


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
    languages = ["en", "mixed"]

    def __init__(self, responses: list[list[Evidence]]) -> None:
        self.responses = list(responses)
        self.queries: list[str] = []

    async def search(self, query: SubQuery) -> list[Evidence]:
        self.queries.append(query.text)
        return self.responses.pop(0)


class ArtifactStoreWithoutLookup:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def store_artifact(
        self,
        *,
        session_id: str,
        kind: str,
        payload: BaseModel,
    ) -> int:
        _ = payload
        self.calls.append((session_id, kind))
        return len(self.calls)

    async def load_artifacts(self, *, session_id: str, kind: str | None = None) -> list[dict]:
        _ = (session_id, kind)
        raise AssertionError(
            "IterationController should not reload artifacts to resolve digest ids."
        )


def make_evidence(url: str, title: str, content: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        content=content,
        source_channel="fake",
        fetched_at=NOW,
    )


def make_digest_payload() -> dict[str, object]:
    return EvidenceDigest(
        topic="Compacted evidence digest",
        key_findings=["Older evidence remains useful"],
        source_urls=[],
        evidence_count=0,
        compressed_at=NOW,
    ).model_dump(mode="json")


def make_subqueries(count: int) -> list[SubQuery]:
    return [
        SubQuery(text=f"subquery {index}", rationale=f"covers slice {index}")
        for index in range(1, count + 1)
    ]


def fake_estimate_tokens(text: str) -> int:
    marker = "[TOKENS="
    if marker not in text:
        return max(len(text.split()), 1) if text else 0
    start = text.index(marker) + len(marker)
    end = text.index("]", start)
    return int(text[start:end])


async def test_iteration_run_stops_after_one_round_when_no_gaps_remain() -> None:
    controller = IterationController()
    channel = FakeChannel(
        [[make_evidence("https://example.com/one", "Pricing update", "pricing update evidence")]]
    )
    client = DummyClient([{"gaps": []}])

    result, research_trace = await controller.run(
        query="pricing update",
        initial_queries=[SubQuery(text="pricing update", rationale="seed query")],
        channels=[channel],
        budget=IterationBudget(max_iterations=1, per_channel_rate_limit=0.0),
        client=client,
    )

    assert channel.queries == ["pricing update"]
    assert [evidence.url for evidence in result] == ["https://example.com/one"]
    assert result[0].score is not None
    assert research_trace == [
        {
            "iteration": 1,
            "batch_index": 1,
            "subqueries": ["pricing update"],
            "gaps": [],
            "digest_id_if_any": None,
        }
    ]
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

    result, research_trace = await controller.run(
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
    assert len(research_trace) == 2
    assert client.calls == 3


async def test_per_search_reflection_called_per_batch(monkeypatch) -> None:
    controller = IterationController()
    channel = FakeChannel(
        [
            [make_evidence(f"https://example.com/{index}", f"Result {index}", "batch evidence")]
            for index in range(1, 6)
        ]
    )
    client = DummyClient([])
    batch_calls: list[list[str]] = []
    follow_up_gaps: list[Gap] = []

    async def fake_per_search_reflect(
        *,
        batch_evidence: list[Evidence],
        query: str,
        client: DummyClient,
        batch_subqueries: list[SubQuery] | None = None,
    ) -> list[Gap]:
        _ = (batch_evidence, query, client)
        batch_number = len(batch_calls) + 1
        batch_calls.append([subquery.text for subquery in batch_subqueries or []])
        return [Gap(topic=f"batch-gap-{batch_number}", reason="fresh batch gap")]

    async def fake_reflect(
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        client: DummyClient,
    ) -> list[Gap]:
        _ = (query, iteration, max_iterations, subqueries, evidences, client)
        return [Gap(topic="iteration-gap", reason="aggregate gap")]

    async def fake_follow_up(
        query: str,
        gaps: list[Gap],
        evidences: list[Evidence],
        client: DummyClient,
    ) -> list[SubQuery]:
        _ = (query, evidences, client)
        follow_up_gaps.extend(gaps)
        return []

    monkeypatch.setattr(controller, "_per_search_reflect", fake_per_search_reflect)
    monkeypatch.setattr(controller, "_reflect", fake_reflect)
    monkeypatch.setattr(controller, "_follow_up", fake_follow_up)

    _, research_trace = await controller.run(
        query="batched search reflection",
        initial_queries=make_subqueries(5),
        channels=[channel],
        budget=IterationBudget(
            max_iterations=2,
            per_channel_rate_limit=0.0,
            subquery_batch_size=3,
        ),
        client=client,
    )

    assert batch_calls == [
        ["subquery 1", "subquery 2", "subquery 3"],
        ["subquery 4", "subquery 5"],
    ]
    assert [gap.topic for gap in follow_up_gaps] == [
        "iteration-gap",
        "batch-gap-1",
        "batch-gap-2",
    ]
    assert [entry["gaps"] for entry in research_trace] == [
        [{"topic": "batch-gap-1", "reason": "fresh batch gap"}],
        [{"topic": "batch-gap-2", "reason": "fresh batch gap"}],
    ]


async def test_compaction_triggered_when_evidence_token_budget_exceeded(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    controller = IterationController()
    channel = FakeChannel(
        [
            [
                make_evidence(
                    f"https://example.com/{index}",
                    f"Result {index}",
                    f"[TOKENS=3000] content {index}",
                )
            ]
            for index in range(1, 5)
        ]
    )
    client = DummyClient([make_digest_payload()])

    async def no_batch_gaps(**_: object) -> list[Gap]:
        return []

    async def no_iteration_gaps(**_: object) -> list[Gap]:
        return []

    monkeypatch.setattr(controller, "_per_search_reflect", no_batch_gaps)
    monkeypatch.setattr(controller, "_reflect", no_iteration_gaps)

    evidences, research_trace = await controller.run(
        query="compact large evidence set",
        initial_queries=make_subqueries(4),
        channels=[channel],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            subquery_batch_size=2,
            context_token_budget=10000,
            compact_hot_set_size=2,
        ),
        client=client,
    )

    assert len(evidences) == 2
    assert evidences[0].score is not None
    assert [entry["digest_id_if_any"] for entry in research_trace] == [None, NOW.isoformat()]
    assert client.calls == 1


async def test_compaction_not_triggered_under_budget(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    controller = IterationController()
    channel = FakeChannel(
        [
            [
                make_evidence(
                    f"https://example.com/{index}",
                    f"Result {index}",
                    f"[TOKENS=1000] content {index}",
                )
            ]
            for index in range(1, 5)
        ]
    )
    client = DummyClient([])

    async def no_batch_gaps(**_: object) -> list[Gap]:
        return []

    async def no_iteration_gaps(**_: object) -> list[Gap]:
        return []

    monkeypatch.setattr(controller, "_per_search_reflect", no_batch_gaps)
    monkeypatch.setattr(controller, "_reflect", no_iteration_gaps)

    evidences, research_trace = await controller.run(
        query="keep evidence under budget",
        initial_queries=make_subqueries(4),
        channels=[channel],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            subquery_batch_size=2,
            context_token_budget=10000,
            compact_hot_set_size=2,
        ),
        client=client,
    )

    assert len(evidences) == 4
    assert all(entry["digest_id_if_any"] is None for entry in research_trace)
    assert client.calls == 0


async def test_research_trace_returned_alongside_evidence(monkeypatch) -> None:
    controller = IterationController()
    channel = FakeChannel(
        [
            [make_evidence(f"https://example.com/{index}", f"Result {index}", "trace evidence")]
            for index in range(1, 9)
        ]
    )
    client = DummyClient([])
    reflect_calls = 0

    async def no_batch_gaps(**_: object) -> list[Gap]:
        return []

    async def fake_reflect(
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        client: DummyClient,
    ) -> list[Gap]:
        _ = (query, iteration, max_iterations, subqueries, evidences, client)
        nonlocal reflect_calls
        reflect_calls += 1
        if reflect_calls == 1:
            return [Gap(topic="continue", reason="run another round")]
        return []

    async def repeat_batches(
        query: str,
        gaps: list[Gap],
        evidences: list[Evidence],
        client: DummyClient,
    ) -> list[SubQuery]:
        _ = (query, gaps, evidences, client)
        return make_subqueries(4)

    monkeypatch.setattr(controller, "_per_search_reflect", no_batch_gaps)
    monkeypatch.setattr(controller, "_reflect", fake_reflect)
    monkeypatch.setattr(controller, "_follow_up", repeat_batches)

    evidences, research_trace = await controller.run(
        query="return research trace",
        initial_queries=make_subqueries(4),
        channels=[channel],
        budget=IterationBudget(
            max_iterations=2,
            per_channel_rate_limit=0.0,
            subquery_batch_size=2,
        ),
        client=client,
    )

    assert isinstance(evidences, list)
    assert isinstance(research_trace, list)
    assert len(research_trace) == 4
    assert [entry["batch_index"] for entry in research_trace] == [1, 2, 1, 2]


async def test_subquery_batch_size_respected(monkeypatch) -> None:
    controller = IterationController()
    client = DummyClient([])
    batch_sizes: list[int] = []

    async def fake_search(
        subqueries: list[SubQuery],
        channels: list[FakeChannel],
        iteration: int,
        priority_channels: set[str] | None = None,
        skip_channels: set[str] | None = None,
    ) -> list[Evidence]:
        _ = (channels, iteration, priority_channels, skip_channels)
        batch_sizes.append(len(subqueries))
        return []

    async def no_batch_gaps(**_: object) -> list[Gap]:
        return []

    async def no_iteration_gaps(**_: object) -> list[Gap]:
        return []

    monkeypatch.setattr(controller, "_search", fake_search)
    monkeypatch.setattr(controller, "_per_search_reflect", no_batch_gaps)
    monkeypatch.setattr(controller, "_reflect", no_iteration_gaps)

    _, research_trace = await controller.run(
        query="batch subqueries",
        initial_queries=make_subqueries(10),
        channels=[FakeChannel([])],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            subquery_batch_size=3,
        ),
        client=client,
    )

    assert batch_sizes == [3, 3, 3, 1]
    assert len(research_trace) == 4


async def test_store_and_session_id_propagated_to_compactor(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    store = await SessionStore.open(":memory:")
    try:
        await store.create_session("session-1", "persist compaction", "deep")
        controller = IterationController(store=store, session_id="session-1")
        channel = FakeChannel(
            [
                [
                    make_evidence(
                        f"https://example.com/{index}",
                        f"Result {index}",
                        f"[TOKENS=3000] content {index}",
                    )
                ]
                for index in range(1, 5)
            ]
        )
        client = DummyClient([make_digest_payload()])

        async def no_batch_gaps(**_: object) -> list[Gap]:
            return []

        async def no_iteration_gaps(**_: object) -> list[Gap]:
            return []

        monkeypatch.setattr(controller, "_per_search_reflect", no_batch_gaps)
        monkeypatch.setattr(controller, "_reflect", no_iteration_gaps)

        _, research_trace = await controller.run(
            query="persist compacted digest",
            initial_queries=make_subqueries(4),
            channels=[channel],
            budget=IterationBudget(
                max_iterations=1,
                per_channel_rate_limit=0.0,
                subquery_batch_size=2,
                context_token_budget=10000,
                compact_hot_set_size=2,
            ),
            client=client,
        )
        digests = await store.load_digests(session_id="session-1")
    finally:
        await store.close()

    assert len(digests) == 1
    assert isinstance(research_trace[-1]["digest_id_if_any"], int)


async def test_digest_trace_id_uses_insert_rowid_without_reload(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    store = ArtifactStoreWithoutLookup()
    controller = IterationController(store=store, session_id="session-1")
    channel = FakeChannel(
        [
            [
                make_evidence(
                    f"https://example.com/{index}",
                    f"Result {index}",
                    f"[TOKENS=3000] content {index}",
                )
            ]
            for index in range(1, 5)
        ]
    )
    client = DummyClient([make_digest_payload()])

    async def no_batch_gaps(**_: object) -> list[Gap]:
        return []

    async def no_iteration_gaps(**_: object) -> list[Gap]:
        return []

    monkeypatch.setattr(controller, "_per_search_reflect", no_batch_gaps)
    monkeypatch.setattr(controller, "_reflect", no_iteration_gaps)

    _, research_trace = await controller.run(
        query="compact using insert rowid",
        initial_queries=make_subqueries(4),
        channels=[channel],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            subquery_batch_size=2,
            context_token_budget=10000,
            compact_hot_set_size=2,
        ),
        client=client,
    )

    assert store.calls == [
        ("session-1", "evicted_evidence"),
        ("session-1", "evicted_evidence"),
        ("session-1", "compacted_digest"),
    ]
    assert research_trace[-1]["digest_id_if_any"] == 3


async def test_backward_compat_when_store_none(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    controller = IterationController()
    channel = FakeChannel(
        [
            [
                make_evidence(
                    f"https://example.com/{index}",
                    f"Result {index}",
                    f"[TOKENS=3000] content {index}",
                )
            ]
            for index in range(1, 5)
        ]
    )
    client = DummyClient([make_digest_payload()])

    async def no_batch_gaps(**_: object) -> list[Gap]:
        return []

    async def no_iteration_gaps(**_: object) -> list[Gap]:
        return []

    monkeypatch.setattr(controller, "_per_search_reflect", no_batch_gaps)
    monkeypatch.setattr(controller, "_reflect", no_iteration_gaps)

    evidences, research_trace = await controller.run(
        query="compact without persistence",
        initial_queries=make_subqueries(4),
        channels=[channel],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            subquery_batch_size=2,
            context_token_budget=10000,
            compact_hot_set_size=2,
        ),
        client=client,
    )

    assert len(evidences) == 2
    assert research_trace[-1]["digest_id_if_any"] == NOW.isoformat()


def test_iteration_budget_is_frozen() -> None:
    budget = IterationBudget()

    with pytest.raises(FrozenInstanceError):
        budget.max_iterations = 2
