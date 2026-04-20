# Self-written, plan v2.3 § 13.5 Progress streaming
from datetime import datetime

from pydantic import BaseModel

from autosearch.core.models import Evidence, SearchMode, SubQuery
from autosearch.core.pipeline import Pipeline

NOW = datetime(2026, 4, 17, 12, 0, 0)


class DummyClient:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = payloads
        self.calls = 0
        self.cost_tracker = None

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        _ = prompt
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


def make_evidence(url: str, title: str, content: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        content=content,
        source_channel="fake",
        fetched_at=NOW,
    )


def make_pipeline(on_event=None) -> Pipeline:
    client = DummyClient(
        [
            {
                "known_facts": ["Typer is a Python CLI framework."],
                "gaps": [{"topic": "Current feature coverage", "reason": "Needs fresh evidence"}],
            },
            {
                "need_clarification": False,
                "question": "",
                "verification": "Research streaming progress coverage.",
                "rubrics": [
                    "Include current behavior",
                    "Use evidence-backed claims",
                    "Explain tradeoffs",
                ],
                "mode": "fast",
                "query_type": "technical",
                "channel_priority": ["fake"],
                "channel_skip": [],
            },
            {
                "subqueries": [
                    {"text": "streaming progress status", "rationale": "baseline"},
                    {"text": "pipeline callback events", "rationale": "coverage"},
                    {"text": "sse event ordering", "rationale": "delivery"},
                ]
            },
            {
                "gaps": [
                    {
                        "topic": "CLI stderr behavior",
                        "reason": "Need a concrete streamed output example",
                    }
                ]
            },
            {
                "subqueries": [
                    {
                        "text": "cli stderr streamed event example",
                        "rationale": "closes the stderr gap",
                    }
                ]
            },
            {"gaps": []},
            {"headings": ["Overview"]},
            {"headings": ["Overview"]},
            {"content": "Streaming is available through the callback path [1].", "ref_ids": [1]},
            {"grade": "pass", "follow_up_gaps": []},
        ]
    )
    channel = FakeChannel(
        [
            [make_evidence("https://example.com/one", "Initial finding", "Callback overview")],
            [make_evidence("https://example.com/two", "CLI notes", "stderr output details")],
            [make_evidence("https://example.com/three", "SSE notes", "event order details")],
            [make_evidence("https://example.com/four", "Follow-up", "async callback details")],
        ]
    )
    return Pipeline(llm=client, channels=[channel], on_event=on_event)


async def test_pipeline_emits_phase_iteration_gap_and_quality_events() -> None:
    events: list[dict[str, object]] = []
    pipeline = make_pipeline(on_event=events.append)

    result = await pipeline.run("How does streaming progress work?", mode_hint=SearchMode.FAST)

    phase_events = [event for event in events if event["type"] == "phase"]
    phase_starts = {(event["phase"], event["status"]) for event in phase_events}
    iteration_events = [event for event in events if event["type"] == "iteration"]

    assert result.delivery_status == "ok"
    assert len(phase_events) >= 10
    assert {
        ("M0", "start"),
        ("M0", "complete"),
        ("M1", "start"),
        ("M1", "complete"),
        ("M2", "start"),
        ("M2", "complete"),
        ("M3", "start"),
        ("M3", "complete"),
        ("M7", "start"),
        ("M7", "complete"),
    } <= phase_starts
    assert iteration_events
    assert events[-1] == {"type": "quality", "grade": "pass", "follow_up_count": 0}


async def test_pipeline_awaits_async_event_callbacks() -> None:
    recorded: list[dict[str, object]] = []

    async def callback(event: dict[str, object]) -> None:
        recorded.append(event)

    pipeline = make_pipeline(on_event=callback)

    await pipeline.run("How does streaming progress work?", mode_hint=SearchMode.FAST)

    assert any(event["type"] == "phase" for event in recorded)
    assert recorded[-1] == {"type": "quality", "grade": "pass", "follow_up_count": 0}


async def test_pipeline_result_includes_channel_empty_calls() -> None:
    client = DummyClient(
        [
            {
                "known_facts": ["Typer is a Python CLI framework."],
                "gaps": [{"topic": "Current feature coverage", "reason": "Needs fresh evidence"}],
            },
            {
                "need_clarification": False,
                "question": "",
                "verification": "Research empty channel result handling.",
                "rubrics": ["Explain observed behavior"],
                "mode": "fast",
            },
            {
                "subqueries": [
                    {"text": "empty channel result behavior", "rationale": "exercise the channel"}
                ]
            },
            {"gaps": []},
            {"headings": ["Overview"]},
            {"headings": ["Overview"]},
            {"grade": "pass", "follow_up_gaps": []},
        ]
    )
    channel = FakeChannel([[]])

    result = await Pipeline(llm=client, channels=[channel]).run(
        "How are empty channel results exposed?",
        mode_hint=SearchMode.FAST,
    )

    assert result.delivery_status == "ok"
    assert result.evidences == []
    assert result.channel_empty_calls == {"fake": 1}


async def test_routing_trace_recorded_on_pipeline_result() -> None:
    pipeline = make_pipeline()

    result = await pipeline.run("How does streaming progress work?", mode_hint=SearchMode.FAST)

    assert result.routing_trace["query_type"] == "technical"
    assert result.routing_trace["priority"] == ["fake"]
    assert result.routing_trace["skip"] == []
    assert result.routing_trace["priority_ran"] == ["fake"]
    assert result.routing_trace["fallback_triggered"] is False
    assert result.routing_trace["priority_evidence_count"] == 4
