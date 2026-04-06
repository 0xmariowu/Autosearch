"""LLM-as-judge deep evaluation for AutoSearch reports.

Adapted from LangChain open_deep_research evaluators.py and prompts.py.

This module defines Pydantic schemas and prompt templates for offline
report quality evaluation. It does NOT call LLMs directly — callers
are responsible for invoking their preferred LLM with structured output.

Usage:
    from lib.quality_eval import (
        OverallQualityScore, GroundednessScore, CompletenessScore,
        format_overall_quality_input, format_groundedness_input,
        format_completeness_input,
        OVERALL_QUALITY_PROMPT, GROUNDEDNESS_PROMPT, COMPLETENESS_PROMPT,
    )
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class OverallQualityScore(BaseModel):
    """Score a research report across six quality dimensions (1-5 each)."""

    research_depth: int = Field(
        description="1-5: thoroughness, coverage, depth of understanding, background context."
    )
    source_quality: int = Field(
        description="1-5: authoritative sources, diversity of source types, citation integration."
    )
    analytical_rigor: int = Field(
        description="1-5: sophistication, critical evaluation, nuances and limitations identified."
    )
    practical_value: int = Field(
        description="1-5: clarity of insights, specific examples, actionable recommendations."
    )
    balance_objectivity: int = Field(
        description="1-5: multiple perspectives, limitations acknowledged, facts vs opinions."
    )
    writing_quality: int = Field(
        description="1-5: clarity, professionalism, terminology, tone consistency, readability."
    )

    def normalize(self) -> dict[str, float]:
        """Return all scores normalized to 0-1 (raw / 5)."""
        return {
            "research_depth": self.research_depth / 5,
            "source_quality": self.source_quality / 5,
            "analytical_rigor": self.analytical_rigor / 5,
            "practical_value": self.practical_value / 5,
            "balance_objectivity": self.balance_objectivity / 5,
            "writing_quality": self.writing_quality / 5,
        }


class GroundednessClaim(BaseModel):
    """A single claim extracted from the report with grounding judgment."""

    claim: str = Field(description="The claim extracted from the report.")
    grounded: bool = Field(description="Whether the claim is grounded in the context.")


class GroundednessScore(BaseModel):
    """Extract claims from a report and check grounding against context."""

    claims: list[GroundednessClaim] = Field(
        description="All claims extracted from the report with grounding judgments."
    )

    def score(self) -> float:
        """Return grounded claims / total claims, or 0.0 if no claims."""
        if not self.claims:
            return 0.0
        grounded = sum(1 for c in self.claims if c.grounded)
        return grounded / len(self.claims)


class CompletenessScore(BaseModel):
    """Score report completeness against the research question."""

    reasoning: str = Field(
        description="Explanation with specific examples from the report."
    )
    score: int = Field(
        description="1-5: how completely the report covers all points from the question."
    )

    def normalize(self) -> float:
        """Return score normalized to 0-1."""
        return self.score / 5


# ---------------------------------------------------------------------------
# Prompts — adapted from open_deep_research/tests/prompts.py
# ---------------------------------------------------------------------------


OVERALL_QUALITY_PROMPT = """You are an expert evaluator assessing the quality of a research report.

Evaluation Criteria:

1. Research Depth and Comprehensiveness
   - Thoroughness of analysis
   - Coverage of aspects relevant to the user's input
   - Depth of understanding
   - Background context provided

2. Source Quality and Methodology
   - Use of authoritative sources
   - Diversity of source types (news, papers, repos, forums)
   - Citation quality and integration
   - Transparency of research methodology

3. Analytical Rigor
   - Sophistication of analysis
   - Critical evaluation of source information
   - Identification of nuances and limitations

4. Practical Value and Actionability
   - Clarity of insights and recommendations
   - Specific examples and use cases
   - Does not refer to itself as the writer of the report

5. Balance and Objectivity
   - Presentation of multiple perspectives
   - Acknowledgment of limitations and trade-offs
   - Distinction between facts and opinions
   - Avoidance of bias

6. Writing Quality and Clarity
   - Clarity and professionalism of writing
   - Appropriate use of terminology
   - Consistency of tone and style
   - Engagement and readability
   - Does not refer to itself as the writer of the report

Scoring: 1 = Poor, 2 = Fair, 3 = Good, 4 = Very Good, 5 = Excellent

Today is {today}

Evaluate the research report now."""


GROUNDEDNESS_PROMPT = """You are evaluating how well a research report is supported by retrieved context.

A well-grounded report should:
- Make claims directly supported by the retrieved context
- Stay within the scope of information provided
- Maintain the same meaning and intent as the source material
- Not introduce external facts or unsupported assertions outside of basic facts

An ungrounded report:
- Makes claims without support from the context
- Contradicts the retrieved information
- Includes speculation or external knowledge outside of basic facts
- Distorts or misrepresents the context

Instructions:
- Compare the report against the retrieved context carefully
- Identify factual claims, statements, and assertions made in the report
- For each claim, decide whether it is directly grounded in the context
- Claims are often made where you see citations — check against the cited source

<context>
{context}
</context>

<report>
{report}
</report>"""


COMPLETENESS_PROMPT = """You are evaluating the completeness of a research report.

A complete report should:
- Answer all points from the user's question
- Cover the full scope of the research topic
- Not make assumptions not directly stated by the user's question

An incomplete report:
- Does not answer all points from the user's question
- Makes assumptions that are not directly stated

Instructions:
- Compare the report against the user's question
- Identify any points that are not covered
- Focus solely on completeness

<user_question>
{user_question}
</user_question>

<report>
{report}
</report>"""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_overall_quality_input(query: str, report: str) -> str:
    """Format user input for overall quality evaluation."""
    return f"User input: {query}\n\nReport:\n\n{report}\n\nEvaluate whether the report meets the criteria."


def format_groundedness_input(context: str, report: str) -> str:
    """Format user input for groundedness evaluation."""
    return GROUNDEDNESS_PROMPT.format(context=context, report=report)


def format_completeness_input(user_question: str, report: str) -> str:
    """Format user input for completeness evaluation."""
    return COMPLETENESS_PROMPT.format(user_question=user_question, report=report)
