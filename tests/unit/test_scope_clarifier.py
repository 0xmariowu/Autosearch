# Self-written, plan autosearch-0419-channels-scope-proxy.md § F101
import pytest
from pydantic import ValidationError

from autosearch.core.scope_clarifier import ScopeClarifier
from autosearch.core.search_scope import SearchScope


def test_questions_for_generates_all_four_when_none_provided() -> None:
    questions = ScopeClarifier().questions_for({})

    assert [question.field for question in questions] == [
        "domain_followups",
        "channel_scope",
        "depth",
        "output_format",
    ]


def test_questions_for_all_provided_returns_empty() -> None:
    questions = ScopeClarifier().questions_for(
        {
            "domain_followups": ["backend"],
            "channel_scope": "mixed",
            "depth": "deep",
            "output_format": "html",
        }
    )

    assert questions == []


def test_questions_for_skips_domain_followups_when_provided() -> None:
    questions = ScopeClarifier().questions_for({"domain_followups": ["backend"]})

    assert [question.field for question in questions] == [
        "channel_scope",
        "depth",
        "output_format",
    ]


def test_questions_for_none_value_triggers_question() -> None:
    questions = ScopeClarifier().questions_for({"domain_followups": ["backend"], "depth": None})

    assert [question.field for question in questions] == [
        "channel_scope",
        "depth",
        "output_format",
    ]


def test_apply_answers_merges_onto_base() -> None:
    base = SearchScope(depth="deep")

    result = ScopeClarifier.apply_answers(base, {"channel_scope": "zh_only"})

    assert result.domain_followups == []
    assert result.depth == "deep"
    assert result.channel_scope == "zh_only"
    assert result.output_format == "md"


def test_apply_answers_parses_comma_separated_domain_followups() -> None:
    result = ScopeClarifier.apply_answers(
        SearchScope(),
        {"domain_followups": "backend, performance, caching"},
    )

    assert result.domain_followups == ["backend", "performance", "caching"]


def test_apply_answers_passes_through_list_domain_followups() -> None:
    result = ScopeClarifier.apply_answers(
        SearchScope(),
        {"domain_followups": ["x", "y"]},
    )

    assert result.domain_followups == ["x", "y"]


def test_apply_answers_handles_empty_domain_followups() -> None:
    result = ScopeClarifier.apply_answers(
        SearchScope(domain_followups=["existing"]),
        {"domain_followups": ""},
    )

    assert result.domain_followups == []


def test_apply_answers_ignores_none_values() -> None:
    base = SearchScope(depth="deep")

    result = ScopeClarifier.apply_answers(base, {"depth": None})

    assert result.depth == "deep"


def test_apply_answers_raises_on_invalid_literal() -> None:
    base = SearchScope()

    with pytest.raises(ValidationError):
        ScopeClarifier.apply_answers(base, {"depth": "invalid"})
