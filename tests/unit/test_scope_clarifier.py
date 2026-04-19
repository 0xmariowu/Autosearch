# Self-written, plan autosearch-0419-channels-scope-proxy.md § F101
import pytest
from pydantic import ValidationError

from autosearch.core.scope_clarifier import ScopeClarifier
from autosearch.core.search_scope import SearchScope


def test_questions_for_empty_returns_three_questions() -> None:
    questions = ScopeClarifier().questions_for({})

    assert [question.field for question in questions] == [
        "channel_scope",
        "depth",
        "output_format",
    ]


def test_questions_for_all_provided_returns_empty() -> None:
    questions = ScopeClarifier().questions_for(
        {
            "channel_scope": "mixed",
            "depth": "deep",
            "output_format": "html",
        }
    )

    assert questions == []


def test_questions_for_partial_skips_provided_fields() -> None:
    questions = ScopeClarifier().questions_for({"depth": "deep"})

    assert [question.field for question in questions] == ["channel_scope", "output_format"]


def test_questions_for_none_value_triggers_question() -> None:
    questions = ScopeClarifier().questions_for({"depth": None})

    assert [question.field for question in questions] == [
        "channel_scope",
        "depth",
        "output_format",
    ]


def test_apply_answers_merges_onto_base() -> None:
    base = SearchScope(depth="deep")

    result = ScopeClarifier.apply_answers(base, {"channel_scope": "zh_only"})

    assert result.depth == "deep"
    assert result.channel_scope == "zh_only"
    assert result.output_format == "md"


def test_apply_answers_ignores_none_values() -> None:
    base = SearchScope(depth="deep")

    result = ScopeClarifier.apply_answers(base, {"depth": None})

    assert result.depth == "deep"


def test_apply_answers_raises_on_invalid_literal() -> None:
    base = SearchScope()

    with pytest.raises(ValidationError):
        ScopeClarifier.apply_answers(base, {"depth": "invalid"})
