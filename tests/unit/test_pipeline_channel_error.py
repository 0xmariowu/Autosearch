# Self-written, plan v2.3 § 13.5
from datetime import UTC, datetime

from pydantic import BaseModel

from autosearch.core.models import Evidence, SearchMode, SubQuery
from autosearch.core.pipeline import Pipeline

NOW = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)


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


class FailingChannel:
    name = "failing"
    languages = ["en", "mixed"]

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: SubQuery) -> list[Evidence]:
        _ = query
        self.calls += 1
        raise RuntimeError("channel boom")


class FakeChannel:
    name = "working"
    languages = ["en", "mixed"]

    def __init__(self, evidences: list[Evidence]) -> None:
        self.evidences = list(evidences)
        self.calls = 0
        self.queries: list[str] = []

    async def search(self, query: SubQuery) -> list[Evidence]:
        self.calls += 1
        self.queries.append(query.text)
        return list(self.evidences)


def _make_evidence(url: str, title: str, content: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet=content[:80],
        content=content,
        source_channel="working",
        fetched_at=NOW,
    )


async def test_pipeline_continues_after_channel_error_and_emits_error_event() -> None:
    """A channel raising in search() is logged, does not abort the run, and surfaces
    as an `on_event({type: "error", ...})` envelope so consumers (CLI stream, SSE) see it."""

    llm = DummyClient(
        [
            {"known_facts": [], "gaps": []},
            {
                "need_clarification": False,
                "question": "",
                "verification": "Proceed with the research request.",
                "rubrics": ["Use evidence"],
                "mode": "fast",
            },
            {
                "subqueries": [
                    {
                        "text": "working query",
                        "rationale": "collect evidence from the healthy channel",
                    }
                ]
            },
            {"gaps": []},
            {"headings": ["Overview"]},
            {"headings": ["Overview"]},
            {"content": "Working evidence supports the answer [1].", "ref_ids": [1]},
            {"grade": "pass", "follow_up_gaps": []},
        ]
    )
    working_evidence = _make_evidence(
        "https://example.com/working",
        "Working evidence",
        "Working evidence content about the query and why it matters.",
    )
    failing_channel = FailingChannel()
    working_channel = FakeChannel(evidences=[working_evidence])
    events: list[dict[str, object]] = []

    result = await Pipeline(
        llm=llm,
        channels=[failing_channel, working_channel],
        on_event=events.append,
    ).run("How should channel failures behave?", mode_hint=SearchMode.FAST)

    assert result.delivery_status == "ok"
    assert [evidence.url for evidence in result.evidences] == ["https://example.com/working"]
    assert result.channel_empty_calls == {}
    assert "Working evidence supports the answer" in (result.markdown or "")
    assert failing_channel.calls == 1
    assert working_channel.calls == 1
    assert working_channel.queries == ["working query"]
    assert any(event["type"] == "iteration" for event in events)
    error_events = [event for event in events if event["type"] == "error"]
    assert len(error_events) == 1
    err = error_events[0]
    assert err["channel"] == "failing"
    assert err["phase"] == "search"
    assert err["subquery"] == "working query"
    assert "channel boom" in err["message"]
