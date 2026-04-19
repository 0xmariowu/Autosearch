# Self-written, plan v2.3 § 13.5
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from autosearch.core.models import (
    ClarifyRequest,
    ClarifyResult,
    Evidence,
    Gap,
    KnowledgeRecall,
    Rubric,
    SearchMode,
    Section,
    SubQuery,
)

FIXED_TIME = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("factory", "field_name", "field_value", "invalid_payload"),
    [
        (
            lambda: SubQuery(text="sqlite fts5 tokenizer", rationale="search strategy seed"),
            "text",
            "updated",
            {"text": None, "rationale": "search strategy seed"},
        ),
        (
            lambda: Evidence(
                url="https://example.com",
                title="Example",
                snippet="snippet",
                content="content",
                source_channel="web",
                fetched_at=FIXED_TIME,
                score=0.8,
            ),
            "title",
            "Updated",
            {
                "url": "https://example.com",
                "title": "Example",
                "snippet": "snippet",
                "content": "content",
                "source_channel": "web",
                "fetched_at": "not-a-date",
                "score": 0.8,
            },
        ),
        (
            lambda: Gap(topic="pricing", reason="needs current vendor data"),
            "reason",
            "changed",
            {"topic": "pricing", "reason": None},
        ),
        (
            lambda: Rubric(text="Includes direct source links"),
            "weight",
            2.0,
            {"text": "Includes direct source links", "weight": "high"},
        ),
        (
            lambda: Section(heading="Summary", content="Answer", ref_ids=[1, 2]),
            "heading",
            "Updated",
            {"heading": "Summary", "content": "Answer", "ref_ids": ["bad"]},
        ),
        (
            lambda: ClarifyRequest(query="best agentic search tools", mode_hint=SearchMode.FAST),
            "query",
            "updated",
            {"query": None, "mode_hint": "fast"},
        ),
        (
            lambda: ClarifyResult(
                need_clarification=False,
                verification="Starting research",
                rubrics=[Rubric(text="Uses recent sources")],
                mode=SearchMode.DEEP,
            ),
            "mode",
            SearchMode.FAST,
            {
                "need_clarification": False,
                "verification": "Starting research",
                "rubrics": ["bad"],
                "mode": "deep",
            },
        ),
        (
            lambda: KnowledgeRecall(
                known_facts=["SQLite FTS5 supports BM25 ranking"],
                gaps=[Gap(topic="Chinese tokenization", reason="needs current implementation")],
            ),
            "known_facts",
            [],
            {"known_facts": "not-a-list", "gaps": []},
        ),
    ],
)
def test_models_validate_and_are_frozen(
    factory: object,
    field_name: str,
    field_value: object,
    invalid_payload: dict[str, object],
) -> None:
    model = factory()

    assert model is not None

    with pytest.raises(ValidationError):
        setattr(model, field_name, field_value)

    with pytest.raises(ValidationError):
        type(model).model_validate(invalid_payload)


def test_search_mode_parses_valid_values() -> None:
    assert SearchMode("fast") is SearchMode.FAST
    assert SearchMode("deep") is SearchMode.DEEP
    assert SearchMode("comprehensive") is SearchMode.COMPREHENSIVE


def test_search_mode_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        SearchMode("slow")
