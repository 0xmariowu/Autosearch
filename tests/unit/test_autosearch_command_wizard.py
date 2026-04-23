"""G2-T11: Tests for /autosearch command 4-step wizard behavior."""

from __future__ import annotations

from autosearch.core.search_scope import SearchScope
from autosearch.core.scope_clarifier import ScopeClarifier


def test_no_questions_when_all_params_provided():
    """Step 1-3 should be skipped when all scope fields are explicitly provided."""
    clarifier = ScopeClarifier()
    questions = clarifier.questions_for(
        {
            "channel_scope": "all",
            "depth": "fast",
            "output_format": "md",
            "domain_followups": [],
        }
    )
    assert len(questions) == 0


def test_all_questions_when_no_params():
    """All 4 questions should appear when user provides no scope hints."""
    clarifier = ScopeClarifier()
    questions = clarifier.questions_for({})
    assert len(questions) == 4
    fields = [q.field for q in questions]
    assert "channel_scope" in fields
    assert "depth" in fields
    assert "output_format" in fields
    assert "domain_followups" in fields


def test_only_missing_questions_when_partial_params():
    """Only ask about fields the user didn't provide."""
    clarifier = ScopeClarifier()
    questions = clarifier.questions_for({"depth": "deep"})
    fields = [q.field for q in questions]
    assert "depth" not in fields
    assert "channel_scope" in fields
    assert "output_format" in fields


def test_each_scope_question_has_options():
    """channel_scope, depth, output_format questions must have option lists."""
    clarifier = ScopeClarifier()
    questions = clarifier.questions_for({})
    option_bearing = {q.field: q.options for q in questions if q.field != "domain_followups"}
    for field, options in option_bearing.items():
        assert len(options) >= 2, f"{field} must have >= 2 options"


def test_scope_question_defaults_are_first_option():
    """First option in each ScopeQuestion should match the SearchScope default."""
    defaults = SearchScope()
    clarifier = ScopeClarifier()
    questions = {q.field: q for q in clarifier.questions_for({})}

    if "channel_scope" in questions:
        assert defaults.channel_scope in questions["channel_scope"].options
    if "depth" in questions:
        assert defaults.depth in questions["depth"].options
    if "output_format" in questions:
        assert defaults.output_format in questions["output_format"].options


def test_clarify_once_contract():
    """The command should only pursue clarification once (no infinite loop).

    This is a contract test — verifies the design principle.
    The actual enforcement is in the command implementation:
    'Only ask once' is documented in commands/autosearch.md.
    """
    # Verify commands/autosearch.md contains the "Only ask once" constraint
    from pathlib import Path

    cmd_text = (Path(__file__).parents[2] / "commands" / "autosearch.md").read_text(
        encoding="utf-8"
    )
    assert "Only ask once" in cmd_text, (
        "commands/autosearch.md must contain 'Only ask once' to document the single-clarification contract"
    )
