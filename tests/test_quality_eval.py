"""Tests for lib/quality_eval.py — LLM-as-judge deep evaluation.

Tests cover schema validation and prompt formatting.
Actual LLM calls are not tested here (they require API keys).
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestOverallQualityScore:
    def test_valid_scores(self):
        from lib.quality_eval import OverallQualityScore

        score = OverallQualityScore(
            research_depth=4,
            source_quality=3,
            analytical_rigor=5,
            practical_value=2,
            balance_objectivity=4,
            writing_quality=3,
        )
        assert score.research_depth == 4
        assert score.writing_quality == 3

    def test_has_six_fields(self):
        import dataclasses

        from lib.quality_eval import OverallQualityScore

        # Exclude internal helper fields (model_fields)
        init_fields = [f for f in dataclasses.fields(OverallQualityScore) if f.init]
        assert len(init_fields) == 6

    def test_field_names(self):
        import dataclasses

        from lib.quality_eval import OverallQualityScore

        expected = {
            "research_depth",
            "source_quality",
            "analytical_rigor",
            "practical_value",
            "balance_objectivity",
            "writing_quality",
        }
        init_fields = {
            f.name for f in dataclasses.fields(OverallQualityScore) if f.init
        }
        assert init_fields == expected

    def test_normalize(self):
        from lib.quality_eval import OverallQualityScore

        score = OverallQualityScore(
            research_depth=5,
            source_quality=5,
            analytical_rigor=5,
            practical_value=5,
            balance_objectivity=5,
            writing_quality=5,
        )
        normalized = score.normalize()
        for value in normalized.values():
            assert value == pytest.approx(1.0)

    def test_normalize_min(self):
        from lib.quality_eval import OverallQualityScore

        score = OverallQualityScore(
            research_depth=1,
            source_quality=1,
            analytical_rigor=1,
            practical_value=1,
            balance_objectivity=1,
            writing_quality=1,
        )
        normalized = score.normalize()
        for value in normalized.values():
            assert value == pytest.approx(0.2)


class TestGroundednessSchemas:
    def test_claim_schema(self):
        from lib.quality_eval import GroundednessClaim

        claim = GroundednessClaim(claim="AI agents can self-improve", grounded=True)
        assert claim.claim == "AI agents can self-improve"
        assert claim.grounded is True

    def test_groundedness_score(self):
        from lib.quality_eval import GroundednessClaim, GroundednessScore

        score = GroundednessScore(
            claims=[
                GroundednessClaim(claim="Claim 1", grounded=True),
                GroundednessClaim(claim="Claim 2", grounded=False),
                GroundednessClaim(claim="Claim 3", grounded=True),
            ]
        )
        assert len(score.claims) == 3
        assert score.score() == pytest.approx(2.0 / 3.0)

    def test_groundedness_empty_claims(self):
        from lib.quality_eval import GroundednessScore

        score = GroundednessScore(claims=[])
        assert score.score() == pytest.approx(0.0)


class TestCompletenessScore:
    def test_schema(self):
        from lib.quality_eval import CompletenessScore

        score = CompletenessScore(reasoning="Covers all aspects", score=4)
        assert score.reasoning == "Covers all aspects"
        assert score.score == 4

    def test_normalize(self):
        from lib.quality_eval import CompletenessScore

        score = CompletenessScore(reasoning="Good", score=4)
        assert score.normalize() == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Prompt formatting tests
# ---------------------------------------------------------------------------


class TestPrompts:
    def test_overall_quality_prompt_has_placeholders(self):
        from lib.quality_eval import OVERALL_QUALITY_PROMPT

        assert "{today}" in OVERALL_QUALITY_PROMPT

    def test_groundedness_prompt_has_placeholders(self):
        from lib.quality_eval import GROUNDEDNESS_PROMPT

        assert "{context}" in GROUNDEDNESS_PROMPT
        assert "{report}" in GROUNDEDNESS_PROMPT

    def test_completeness_prompt_has_placeholders(self):
        from lib.quality_eval import COMPLETENESS_PROMPT

        assert "{user_question}" in COMPLETENESS_PROMPT
        assert "{report}" in COMPLETENESS_PROMPT

    def test_format_overall_prompt(self):
        from lib.quality_eval import format_overall_quality_input

        result = format_overall_quality_input(
            query="What are AI agent frameworks?",
            report="# Report\nContent here.",
        )
        assert "What are AI agent frameworks?" in result
        assert "Content here." in result

    def test_format_groundedness_input(self):
        from lib.quality_eval import format_groundedness_input

        result = format_groundedness_input(
            context="Source material here.",
            report="# Report\nClaims here.",
        )
        assert "Source material here." in result
        assert "Claims here." in result

    def test_format_completeness_input(self):
        from lib.quality_eval import format_completeness_input

        result = format_completeness_input(
            user_question="Compare X and Y",
            report="# Report\nComparison here.",
        )
        assert "Compare X and Y" in result
        assert "Comparison here." in result
