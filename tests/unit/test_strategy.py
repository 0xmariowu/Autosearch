# Self-written, plan v2.3 § 13.5
from pydantic import BaseModel

from autosearch.core.models import ClarifyResult, Gap, KnowledgeRecall, Rubric, SearchMode, SubQuery
from autosearch.core.strategy import QueryStrategist


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


def make_clarify() -> ClarifyResult:
    return ClarifyResult(
        need_clarification=False,
        verification="Compare the latest search tooling tradeoffs for engineers.",
        rubrics=[
            Rubric(text="Covers pricing changes", weight=1.0),
            Rubric(text="Compares ranking quality", weight=1.5),
        ],
        mode=SearchMode.DEEP,
    )


def make_recall(gaps: list[Gap] | None = None) -> KnowledgeRecall:
    return KnowledgeRecall(
        known_facts=["BM25 is widely used for lexical ranking."],
        gaps=gaps if gaps is not None else [Gap(topic="Recent pricing", reason="Needs fresh data")],
    )


async def test_generate_subqueries_returns_exact_requested_count() -> None:
    client = DummyClient(
        [
            {
                "subqueries": [
                    {"text": "search ranking bm25 comparison", "rationale": "covers ranking"},
                    {"text": "search api pricing 2026", "rationale": "covers pricing"},
                    {"text": "search latency benchmarks", "rationale": "extra query"},
                ]
            }
        ]
    )

    result = await QueryStrategist().generate_subqueries(
        make_clarify(),
        make_recall(),
        client,
        n=2,
    )

    assert result == [
        SubQuery(text="search ranking bm25 comparison", rationale="covers ranking"),
        SubQuery(text="search api pricing 2026", rationale="covers pricing"),
    ]
    assert client.calls == 1


async def test_generate_subqueries_includes_rubrics_and_gaps_in_prompt() -> None:
    client = DummyClient(
        [{"subqueries": [{"text": "search api pricing 2026", "rationale": "covers pricing"}]}]
    )

    await QueryStrategist().generate_subqueries(make_clarify(), make_recall(), client, n=1)

    prompt = client.prompts[0]
    assert "Rubrics:" in prompt
    assert "- Covers pricing changes (weight=1.0)" in prompt
    assert "- Compares ranking quality (weight=1.5)" in prompt
    assert "Known gaps from pre-recall:" in prompt
    assert "- Recent pricing: Needs fresh data" in prompt


async def test_generate_subqueries_allows_empty_gap_list() -> None:
    client = DummyClient(
        [{"subqueries": [{"text": "bm25 search quality", "rationale": "covers known facts"}]}]
    )

    result = await QueryStrategist().generate_subqueries(
        make_clarify(),
        make_recall(gaps=[]),
        client,
        n=1,
    )

    assert result == [SubQuery(text="bm25 search quality", rationale="covers known facts")]
    assert "Known gaps from pre-recall:\n- None provided" in client.prompts[0]
