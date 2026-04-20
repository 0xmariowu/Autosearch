# Self-written, plan v2.3 § W3 F302
from pydantic import BaseModel

from autosearch.core.models import OutlineNode, ResearchTurn
from autosearch.synthesis.outline import OutlineResponse, draft_outline, refine_outline


class FakeLLMClient:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = list(payloads)
        self.calls = 0
        self.prompts: list[str] = []
        self.response_models: list[type[BaseModel]] = []

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.prompts.append(prompt)
        self.response_models.append(response_model)
        payload = self.payloads[self.calls]
        self.calls += 1
        return response_model.model_validate(payload)


async def test_draft_outline_returns_tree_from_query() -> None:
    client = FakeLLMClient([OutlineResponse(markdown="# A\n## A1\n# B").model_dump(mode="json")])

    outline = await draft_outline("search tooling", client)

    assert outline.heading == ""
    assert outline.level == 0
    assert [child.heading for child in outline.children] == ["A", "B"]
    assert [child.heading for child in outline.children[0].children] == ["A1"]
    assert client.response_models == [OutlineResponse]


async def test_draft_outline_fallback_on_parse_failure() -> None:
    client = FakeLLMClient([{"markdown": "garbage", "headings": []}])

    outline = await draft_outline("search tooling", client)

    assert outline == OutlineNode(heading="search tooling", level=1)


async def test_refine_outline_accepts_dict_research_trace() -> None:
    client = FakeLLMClient(
        [OutlineResponse(markdown="# Final\n## Evidence").model_dump(mode="json")]
    )
    draft = OutlineNode(
        heading="",
        level=0,
        children=[OutlineNode(heading="Draft", level=1)],
    )
    research_trace = [
        {
            "iteration": 1,
            "batch_index": 0,
            "subqueries": ["pricing comparison", "latency comparison"],
            "gaps": [{"topic": "regional support", "reason": "coverage still missing"}],
            "digest_id_if_any": 42,
        }
    ]

    outline = await refine_outline("compare providers", draft, research_trace, client)

    assert outline.heading == "Final"
    assert [child.heading for child in outline.children] == ["Evidence"]
    assert "Turn 1 (iteration 1, batch 0):" in client.prompts[0]
    assert "Q: pricing comparison; latency comparison" in client.prompts[0]
    assert "A: Observed gaps: regional support (coverage still missing)" in client.prompts[0]
    assert "Searched: pricing comparison; latency comparison" in client.prompts[0]


async def test_refine_outline_accepts_typed_research_trace() -> None:
    client = FakeLLMClient(
        [OutlineResponse(markdown="# Final\n## Coverage").model_dump(mode="json")]
    )
    draft = OutlineNode(heading="Draft", level=1)
    research_trace = [
        ResearchTurn(
            iteration=2,
            batch_index=1,
            question="Which providers had current benchmarks?",
            answer="Two providers had 2026 benchmark notes.",
            search_queries=["provider benchmark 2026", "provider latency note"],
            evidence_ids=["e-1", "e-2"],
        )
    ]

    outline = await refine_outline("compare providers", draft, research_trace, client)

    assert outline.heading == "Final"
    assert [child.heading for child in outline.children] == ["Coverage"]
    assert "Turn 1 (iteration 2, batch 1):" in client.prompts[0]
    assert "Q: Which providers had current benchmarks?" in client.prompts[0]
    assert "A: Two providers had 2026 benchmark notes." in client.prompts[0]
    assert "Searched: provider benchmark 2026; provider latency note" in client.prompts[0]


async def test_refine_outline_truncates_large_trace() -> None:
    client = FakeLLMClient([OutlineResponse(markdown="# Final").model_dump(mode="json")])
    draft = OutlineNode(heading="Draft", level=1)
    research_trace = [
        ResearchTurn(
            iteration=index,
            batch_index=index % 3,
            question=f"Question {index} " + ("x" * 120),
            answer=f"Answer {index} " + ("y" * 180),
            search_queries=[f"query {index} " + ("z" * 80)],
            evidence_ids=[f"e-{index}"],
        )
        for index in range(1, 101)
    ]

    outline = await refine_outline("compare providers", draft, research_trace, client)

    assert outline.heading == "Final"
    assert len(client.prompts[0]) < 9800
    assert "Turn 100" in client.prompts[0]
    assert "Turn 1 (iteration 1, batch 1):" not in client.prompts[0]


async def test_refine_outline_preserves_draft_when_trace_empty() -> None:
    client = FakeLLMClient([])
    draft = OutlineNode(
        heading="",
        level=0,
        children=[
            OutlineNode(
                heading="Overview",
                level=1,
                children=[OutlineNode(heading="History", level=2)],
            )
        ],
    )

    refined = await refine_outline("compare providers", draft, [], client)

    assert refined == draft
    assert client.prompts == []
