# Self-written, plan autosearch-0419-channels-scope-proxy.md § F101
import pytest
from pydantic import ValidationError

from autosearch.core.search_scope import ScopeQuestion, SearchScope


def test_search_scope_defaults() -> None:
    scope = SearchScope()

    assert scope.domain_followups == []
    assert scope.channel_scope == "all"
    assert scope.depth == "fast"
    assert scope.output_format == "md"
    assert SearchScope.model_config["frozen"] is True


def test_search_scope_validates_channel_scope_literal() -> None:
    with pytest.raises(ValidationError):
        SearchScope(channel_scope="bogus")


def test_search_scope_validates_depth_literal() -> None:
    with pytest.raises(ValidationError):
        SearchScope(depth="bogus")


def test_search_scope_validates_output_format_literal() -> None:
    with pytest.raises(ValidationError):
        SearchScope(output_format="bogus")


def test_search_scope_frozen_rejects_mutation() -> None:
    scope = SearchScope()

    with pytest.raises(ValidationError):
        scope.depth = "deep"


def test_scope_question_frozen_and_serializable() -> None:
    question = ScopeQuestion(
        field="depth",
        prompt="How deep should the search go?",
        options=["fast", "deep", "comprehensive"],
    )

    dumped = question.model_dump()
    loaded = ScopeQuestion.model_validate(dumped)

    assert ScopeQuestion.model_config["frozen"] is True
    assert loaded == question
