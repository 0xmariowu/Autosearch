"""G2-T12: Tests for ScopeClarifier defaults and skip-all behavior."""

from __future__ import annotations

from autosearch.core.scope_clarifier import ScopeClarifier
from autosearch.core.search_scope import SearchScope


def test_full_skip_all_path():
    """When every scope field is already set, zero questions are generated."""
    clarifier = ScopeClarifier()
    full = {
        "channel_scope": "all",
        "depth": "fast",
        "output_format": "md",
        "domain_followups": [],
    }
    assert clarifier.questions_for(full) == []


def test_default_values_are_valid_scope():
    """SearchScope() default values must satisfy all ScopeQuestion option lists."""
    defaults = SearchScope()
    clarifier = ScopeClarifier()
    questions = clarifier.questions_for({})

    for q in questions:
        if not q.options:
            continue
        field_default = getattr(defaults, q.field, None)
        if field_default is None:
            continue
        # For list fields (domain_followups), skip the options check
        if isinstance(field_default, list):
            continue
        assert field_default in q.options, (
            f"Default value '{field_default}' for field '{q.field}' "
            f"is not in question options: {q.options}"
        )


def test_apply_answers_produces_valid_scope():
    """Applying answers from all questions should produce a valid SearchScope."""
    clarifier = ScopeClarifier()
    questions = clarifier.questions_for({})

    # Pick first option for each question that has options
    answers = {}
    for q in questions:
        if q.options:
            answers[q.field] = q.options[0]
        elif q.field == "domain_followups":
            answers[q.field] = ""

    scope = clarifier.apply_answers(SearchScope(), answers)
    assert isinstance(scope, SearchScope)
    assert scope.channel_scope in ("all", "en_only", "zh_only", "mixed")
    assert scope.depth in ("fast", "deep", "comprehensive")
    assert scope.output_format in ("md", "html")


def test_depth_question_has_three_options():
    """Depth must have exactly fast/deep/comprehensive."""
    clarifier = ScopeClarifier()
    questions = {q.field: q for q in clarifier.questions_for({})}
    assert "depth" in questions
    opts = questions["depth"].options
    assert "fast" in opts
    assert "deep" in opts
    assert "comprehensive" in opts


def test_output_format_has_md_and_html():
    """Output format must include md and html."""
    clarifier = ScopeClarifier()
    questions = {q.field: q for q in clarifier.questions_for({})}
    assert "output_format" in questions
    opts = questions["output_format"].options
    assert "md" in opts
    assert "html" in opts
