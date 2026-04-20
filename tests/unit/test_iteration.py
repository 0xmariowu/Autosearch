# Self-written, plan v2.3 § 13.5
import asyncio
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

import autosearch.core.iteration as iteration_module
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


class RecordingLogger:
    def __init__(self) -> None:
        self.info_calls: list[tuple[str, dict[str, object]]] = []
        self.warning_calls: list[tuple[str, dict[str, object]]] = []

    def info(self, event: str, **kwargs: object) -> None:
        self.info_calls.append((event, kwargs))

    def warning(self, event: str, **kwargs: object) -> None:
        self.warning_calls.append((event, kwargs))


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


async def test_iteration_single_perspective_backward_compat(monkeypatch) -> None:
    controller = IterationController()
    channel = FakeChannel(
        [[make_evidence("https://example.com/one", "Pricing update", "pricing update evidence")]]
    )
    client = DummyClient([])
    generate_calls = 0

    async def fake_generate_perspectives(
        query: str,
        client: DummyClient,
        *,
        num_perspectives: int = 3,
    ) -> list[str]:
        _ = (query, client, num_perspectives)
        nonlocal generate_calls
        generate_calls += 1
        return ["economic feasibility", "environmental impact", "policy implementation"]

    async def fake_reflect(
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        client: DummyClient,
    ) -> list[Gap]:
        _ = (query, iteration, max_iterations, subqueries, evidences, client)
        return []

    monkeypatch.setattr(iteration_module, "generate_perspectives", fake_generate_perspectives)
    monkeypatch.setattr(controller, "_reflect", fake_reflect)

    _, research_trace = await controller.run(
        query="pricing update",
        initial_queries=[SubQuery(text="pricing update", rationale="seed query")],
        channels=[channel],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            num_perspectives=0,
        ),
        client=client,
    )

    assert generate_calls == 0
    assert research_trace == [
        {
            "iteration": 1,
            "batch_index": 1,
            "subqueries": ["pricing update"],
            "gaps": [],
            "digest_id_if_any": None,
        }
    ]


async def test_iteration_multi_perspective_reflects_in_parallel(monkeypatch) -> None:
    controller = IterationController()
    channel = FakeChannel(
        [
            [
                make_evidence(
                    "https://example.com/one",
                    "Perspective update",
                    "perspective evidence",
                )
            ]
        ]
    )
    client = DummyClient([])
    perspectives = [
        "economic feasibility",
        "environmental impact",
        "policy implementation",
    ]
    call_perspectives: list[str] = []
    active_calls = 0
    max_active_calls = 0

    async def fake_generate_perspectives(
        query: str,
        client: DummyClient,
        *,
        num_perspectives: int = 3,
    ) -> list[str]:
        _ = (query, client, num_perspectives)
        return perspectives

    async def fake_reflect_for_perspective(
        *,
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        perspective: str | None,
        client: DummyClient,
    ) -> list[Gap]:
        _ = (query, iteration, max_iterations, subqueries, evidences, client)
        assert perspective is not None
        nonlocal active_calls, max_active_calls
        call_perspectives.append(perspective)
        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        await asyncio.sleep(0.01)
        active_calls -= 1
        return [Gap(topic=f"{perspective} gap", reason="perspective-specific gap")]

    monkeypatch.setattr(iteration_module, "generate_perspectives", fake_generate_perspectives)
    monkeypatch.setattr(controller, "_reflect_for_perspective", fake_reflect_for_perspective)

    _, research_trace = await controller.run(
        query="renewable energy adoption",
        initial_queries=[SubQuery(text="renewable energy adoption", rationale="seed query")],
        channels=[channel],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            num_perspectives=3,
        ),
        client=client,
    )

    assert set(call_perspectives) == set(perspectives)
    assert len(call_perspectives) == 3
    assert max_active_calls >= 2
    assert research_trace[0]["perspective"] == perspectives


async def test_iteration_multi_perspective_gaps_deduplicated(monkeypatch) -> None:
    controller = IterationController()
    channel = FakeChannel(
        [[make_evidence("https://example.com/one", "Pricing update", "pricing update evidence")]]
    )
    client = DummyClient([])
    follow_up_gaps: list[Gap] = []

    async def fake_generate_perspectives(
        query: str,
        client: DummyClient,
        *,
        num_perspectives: int = 3,
    ) -> list[str]:
        _ = (query, client, num_perspectives)
        return ["economic feasibility", "environmental impact"]

    async def fake_reflect_multi_perspective(
        *,
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        perspectives: list[str],
        client: DummyClient,
    ) -> dict[str, list[Gap]]:
        _ = (query, iteration, max_iterations, subqueries, evidences, perspectives, client)
        return {
            "economic feasibility": [Gap(topic="grid costs", reason="Need updated capex numbers")],
            "environmental impact": [Gap(topic="grid costs", reason="Need updated capex numbers")],
        }

    async def fake_follow_up(
        query: str,
        gaps: list[Gap],
        evidences: list[Evidence],
        client: DummyClient,
    ) -> list[SubQuery]:
        _ = (query, evidences, client)
        follow_up_gaps.extend(gaps)
        return []

    monkeypatch.setattr(iteration_module, "generate_perspectives", fake_generate_perspectives)
    monkeypatch.setattr(controller, "_reflect_multi_perspective", fake_reflect_multi_perspective)
    monkeypatch.setattr(controller, "_follow_up", fake_follow_up)

    await controller.run(
        query="renewable energy adoption",
        initial_queries=[SubQuery(text="renewable energy adoption", rationale="seed query")],
        channels=[channel],
        budget=IterationBudget(
            max_iterations=2,
            per_channel_rate_limit=0.0,
            num_perspectives=3,
        ),
        client=client,
    )

    assert follow_up_gaps == [Gap(topic="grid costs", reason="Need updated capex numbers")]


async def test_iteration_multi_perspective_research_trace_tags_perspective(
    monkeypatch,
) -> None:
    controller = IterationController()
    channel = FakeChannel(
        [[make_evidence("https://example.com/one", "Pricing update", "pricing update evidence")]]
    )
    client = DummyClient([])
    perspectives = [
        "economic feasibility",
        "environmental impact",
        "policy implementation",
    ]

    async def fake_generate_perspectives(
        query: str,
        client: DummyClient,
        *,
        num_perspectives: int = 3,
    ) -> list[str]:
        _ = (query, client, num_perspectives)
        return perspectives

    async def fake_reflect_multi_perspective(**_: object) -> dict[str, list[Gap]]:
        return {perspective: [] for perspective in perspectives}

    monkeypatch.setattr(iteration_module, "generate_perspectives", fake_generate_perspectives)
    monkeypatch.setattr(controller, "_reflect_multi_perspective", fake_reflect_multi_perspective)

    _, research_trace = await controller.run(
        query="renewable energy adoption",
        initial_queries=[SubQuery(text="renewable energy adoption", rationale="seed query")],
        channels=[channel],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            num_perspectives=3,
        ),
        client=client,
    )

    assert research_trace == [
        {
            "iteration": 1,
            "batch_index": 1,
            "subqueries": ["renewable energy adoption"],
            "gaps": [],
            "digest_id_if_any": None,
            "perspective": perspectives,
        }
    ]


async def test_iteration_batch_log_includes_perspective_mode(monkeypatch) -> None:
    controller = IterationController()
    logger = RecordingLogger()
    monkeypatch.setattr(controller, "logger", logger)
    channel = FakeChannel(
        [
            [make_evidence("https://example.com/one", "First result", "first evidence")],
            [make_evidence("https://example.com/two", "Second result", "second evidence")],
        ]
    )
    client = DummyClient([])
    perspectives = [
        "economic feasibility",
        "environmental impact",
    ]

    async def fake_generate_perspectives(
        query: str,
        client: DummyClient,
        *,
        num_perspectives: int = 3,
    ) -> list[str]:
        _ = (query, client, num_perspectives)
        return perspectives

    async def fake_per_search_reflect_multi_perspective(
        *,
        batch_evidence: list[Evidence],
        query: str,
        client: DummyClient,
        batch_subqueries: list[SubQuery] | None = None,
        perspectives: list[str],
    ) -> dict[str, list[Gap]]:
        _ = (batch_evidence, query, client, batch_subqueries)
        return {perspective: [] for perspective in perspectives}

    async def fake_reflect_multi_perspective(
        *,
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        perspectives: list[str],
        client: DummyClient,
    ) -> dict[str, list[Gap]]:
        _ = (query, iteration, max_iterations, subqueries, evidences, client)
        return {perspective: [] for perspective in perspectives}

    monkeypatch.setattr(iteration_module, "generate_perspectives", fake_generate_perspectives)
    monkeypatch.setattr(
        controller,
        "_per_search_reflect_multi_perspective",
        fake_per_search_reflect_multi_perspective,
    )
    monkeypatch.setattr(controller, "_reflect_multi_perspective", fake_reflect_multi_perspective)

    await controller.run(
        query="renewable energy adoption",
        initial_queries=make_subqueries(2),
        channels=[channel],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            subquery_batch_size=1,
            num_perspectives=3,
        ),
        client=client,
    )

    batch_completed_calls = [
        kwargs for event, kwargs in logger.info_calls if event == "iteration_batch_completed"
    ]
    assert len(batch_completed_calls) == 2
    assert all(call["perspective_mode"] == "multi" for call in batch_completed_calls)
    assert all(call["num_perspectives"] == 2 for call in batch_completed_calls)

    reflect_completed_calls = [
        kwargs
        for event, kwargs in logger.info_calls
        if event == "iteration_phase_completed" and kwargs.get("phase") == "reflect"
    ]
    assert len(reflect_completed_calls) == 1
    assert reflect_completed_calls[0]["perspective_mode"] == "multi"
    assert reflect_completed_calls[0]["num_perspectives"] == 2


async def test_iteration_perspective_generation_error_fallback_runs_single(
    monkeypatch,
) -> None:
    controller = IterationController()
    channel = FakeChannel(
        [[make_evidence("https://example.com/one", "Pricing update", "pricing update evidence")]]
    )
    client = DummyClient([])
    single_reflect_calls = 0
    multi_reflect_calls = 0

    async def fake_generate_perspectives(
        query: str,
        client: DummyClient,
        *,
        num_perspectives: int = 3,
    ) -> list[str]:
        _ = (query, client, num_perspectives)
        return ["default"]

    async def fake_reflect(
        query: str,
        iteration: int,
        max_iterations: int,
        subqueries: list[SubQuery],
        evidences: list[Evidence],
        client: DummyClient,
    ) -> list[Gap]:
        _ = (query, iteration, max_iterations, subqueries, evidences, client)
        nonlocal single_reflect_calls
        single_reflect_calls += 1
        return []

    async def fake_reflect_multi_perspective(**_: object) -> dict[str, list[Gap]]:
        nonlocal multi_reflect_calls
        multi_reflect_calls += 1
        return {"default": []}

    monkeypatch.setattr(iteration_module, "generate_perspectives", fake_generate_perspectives)
    monkeypatch.setattr(controller, "_reflect", fake_reflect)
    monkeypatch.setattr(controller, "_reflect_multi_perspective", fake_reflect_multi_perspective)

    _, research_trace = await controller.run(
        query="renewable energy adoption",
        initial_queries=[SubQuery(text="renewable energy adoption", rationale="seed query")],
        channels=[channel],
        budget=IterationBudget(
            max_iterations=1,
            per_channel_rate_limit=0.0,
            num_perspectives=3,
        ),
        client=client,
    )

    assert single_reflect_calls == 1
    assert multi_reflect_calls == 0
    assert "perspective" not in research_trace[0]
