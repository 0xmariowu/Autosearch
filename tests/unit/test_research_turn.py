# Self-written, plan v2.3 § 13.5 F301
from autosearch.core.models import ResearchTurn


def test_research_turn_minimum_fields() -> None:
    turn = ResearchTurn(
        iteration=1,
        question="What changed in the API?",
        answer="The release adds a new endpoint and updates auth guidance.",
    )

    assert turn.batch_index == 0
    assert turn.perspective is None
    assert turn.search_queries == []
    assert turn.evidence_ids == []
    assert turn.digest_trace_id is None


def test_research_turn_full_fields() -> None:
    turn = ResearchTurn(
        iteration=2,
        batch_index=1,
        perspective="security reviewer",
        question="Are there migration risks?",
        answer="The docs mention a deprecation window and fallback path.",
        search_queries=["api migration risks", "deprecation window"],
        evidence_ids=["https://example.com/guide", "session-evidence-2"],
        digest_trace_id=42,
    )

    payload = turn.model_dump_json()
    restored = ResearchTurn.model_validate_json(payload)

    assert restored == turn


def test_research_turn_perspective_default_none() -> None:
    turn = ResearchTurn(
        iteration=3,
        question="What does the changelog say?",
        answer="The changelog confirms the feature is GA.",
    )

    assert turn.perspective is None
