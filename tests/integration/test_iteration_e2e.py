# Self-written, plan 0420 W2 F203
from datetime import UTC, datetime

from pydantic import BaseModel

from autosearch.core import context_compaction as context_compaction_module
from autosearch.core.iteration import IterationBudget, IterationController
from autosearch.core.models import Evidence, EvidenceDigest, SubQuery
from tests.fixtures.fake_channel import FakeChannel

NOW = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)


class IterationClient:
    def __init__(self) -> None:
        self.iteration_gap_calls = 0
        self.follow_up_calls = 0
        self.compaction_calls = 0

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        if response_model is EvidenceDigest:
            self.compaction_calls += 1
            return response_model.model_validate(
                EvidenceDigest(
                    topic="Older evidence digest",
                    key_findings=["Older evidence was compacted"],
                    source_urls=[],
                    evidence_count=0,
                    compressed_at=NOW,
                ).model_dump(mode="json")
            )

        if response_model.__name__ == "_GapReflectionResponse":
            if "<Current iteration>" in prompt:
                self.iteration_gap_calls += 1
                return response_model.model_validate(
                    {
                        "gaps": [
                            {
                                "topic": f"follow-up topic {self.iteration_gap_calls}",
                                "reason": "keep the research loop moving",
                            }
                        ]
                    }
                )
            return response_model.model_validate({"gaps": []})

        if response_model.__name__ == "_FollowUpQueryResponse":
            self.follow_up_calls += 1
            return response_model.model_validate(
                {
                    "subqueries": [
                        {
                            "text": f"follow up query {self.follow_up_calls}",
                            "rationale": "continue the deep search",
                        }
                    ]
                }
            )

        raise AssertionError(f"Unexpected response model: {response_model.__name__}")


def fake_estimate_tokens(text: str) -> int:
    marker = "[TOKENS="
    if marker not in text:
        return max(len(text.split()), 1) if text else 0
    start = text.index(marker) + len(marker)
    end = text.index("]", start)
    return int(text[start:end])


def make_evidence(query: SubQuery, call_index: int) -> list[Evidence]:
    return [
        Evidence(
            url=f"https://example.com/{call_index}",
            title=f"Evidence {call_index}",
            snippet=f"Snippet for {query.text}",
            content=f"[TOKENS=3000] Evidence body for {query.text}",
            source_channel="web",
            fetched_at=NOW,
        )
    ]


async def test_iteration_runs_full_cycle_with_compaction(monkeypatch) -> None:
    monkeypatch.setattr(context_compaction_module, "estimate_tokens", fake_estimate_tokens)
    controller = IterationController()
    client = IterationClient()
    call_index = 0

    def factory(query: SubQuery) -> list[Evidence]:
        nonlocal call_index
        call_index += 1
        return make_evidence(query, call_index)

    channel = FakeChannel(name="web", factory=factory)
    budget = IterationBudget(
        max_iterations=5,
        per_channel_rate_limit=0.0,
        subquery_batch_size=2,
        context_token_budget=16000,
        compact_hot_set_size=3,
        compact_trigger_pct=0.8,
    )

    evidences, research_trace = await controller.run(
        query="deep iteration compaction flow",
        initial_queries=[
            SubQuery(text="initial topic 1", rationale="seed"),
            SubQuery(text="initial topic 2", rationale="seed"),
            SubQuery(text="initial topic 3", rationale="seed"),
            SubQuery(text="initial topic 4", rationale="seed"),
        ],
        channels=[channel],
        budget=budget,
        client=client,
    )

    assert client.iteration_gap_calls == 5
    assert client.compaction_calls >= 1
    assert len(evidences) <= budget.compact_hot_set_size + 2
    assert any(entry["digest_id_if_any"] is not None for entry in research_trace)
