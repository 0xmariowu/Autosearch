# Self-written, plan autosearch-0419-channels-scope-proxy.md § F101
import pytest
from pydantic import ValidationError

from autosearch.core.search_scope import ScopeQuestion, SearchScope, filter_channels_by_scope


class _Channel:
    def __init__(self, name: str, languages: list[str]) -> None:
        self.name = name
        self.languages = languages


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


def test_filter_channels_all_keeps_all() -> None:
    channels = [_Channel("en", ["en"]), _Channel("zh", ["zh"])]

    filtered = filter_channels_by_scope(channels, "all")

    assert filtered == channels


def test_filter_channels_en_only_drops_zh_only_channels() -> None:
    channels = [
        _Channel("en", ["en"]),
        _Channel("zh", ["zh"]),
        _Channel("zh_mixed", ["zh", "mixed"]),
    ]

    filtered = filter_channels_by_scope(channels, "en_only")

    assert [channel.name for channel in filtered] == ["en"]


def test_filter_channels_zh_only_drops_en_only_channels() -> None:
    channels = [
        _Channel("en", ["en"]),
        _Channel("en_mixed", ["en", "mixed"]),
        _Channel("zh", ["zh"]),
    ]

    filtered = filter_channels_by_scope(channels, "zh_only")

    assert [channel.name for channel in filtered] == ["zh"]


def test_filter_channels_mixed_is_noop() -> None:
    channels = [_Channel("en", ["en"]), _Channel("zh", ["zh"])]

    filtered = filter_channels_by_scope(channels, "mixed")

    assert filtered == channels


def test_filter_channels_bilingual_channel_kept_for_both() -> None:
    bilingual = _Channel("bilingual", ["en", "zh", "mixed"])
    channels = [_Channel("en", ["en"]), bilingual, _Channel("zh", ["zh"])]

    en_filtered = filter_channels_by_scope(channels, "en_only")
    zh_filtered = filter_channels_by_scope(channels, "zh_only")

    assert bilingual in en_filtered
    assert bilingual in zh_filtered
