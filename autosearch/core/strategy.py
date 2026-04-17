# Source: gpt-researcher/gpt_researcher/prompts.py:L213-L255 (adapted)
# Source: gpt-researcher/gpt_researcher/actions/query_processing.py:L37-L80 (adapted)
from datetime import datetime, timezone
from textwrap import dedent

import structlog
from pydantic import BaseModel, Field

from autosearch.core.models import ClarifyResult, KnowledgeRecall, SubQuery
from autosearch.llm.client import LLMClient

SEARCH_QUERY_PROMPT = dedent(
    """\
    Write {n} search queries to search online that form an objective view of the following task:
    "{task}"

    Assume the current date is {today} if required.

    Context:
    {context}

    Use this context to inform and refine your search queries. The context provides task guidance,
    evaluation criteria, and known information gaps that should shape more specific and relevant
    searches.

    Respond in valid JSON with this exact schema:
    {{
      "subqueries": [
        {{
          "text": "search query",
          "rationale": "why this query helps cover the task"
        }}
      ]
    }}

    Rules:
    - Return exactly {n} subqueries
    - Make the queries mutually complementary rather than redundant
    - Prefer concrete search terms over vague natural-language questions
    - Use current-year or date terms only when the task is time-sensitive
    - Keep each rationale concise and specific
    """
).strip()


class _SubQueryBatch(BaseModel):
    subqueries: list[SubQuery] = Field(default_factory=list)


class QueryStrategist:
    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="query_strategist")

    async def generate_subqueries(
        self,
        clarify: ClarifyResult,
        recall: KnowledgeRecall,
        client: LLMClient,
        n: int = 5,
    ) -> list[SubQuery]:
        if n <= 0:
            return []

        task = _build_task(clarify)
        context = _build_context(clarify, recall)
        prompt = SEARCH_QUERY_PROMPT.format(
            n=n,
            task=task,
            today=datetime.now(timezone.utc).strftime("%B %d, %Y"),
            context=context,
        )
        self.logger.info(
            "subquery_generation_started",
            mode=clarify.mode.value,
            rubrics=len(clarify.rubrics),
            gaps=len(recall.gaps),
            requested=n,
        )
        completion = await client.complete(prompt, _SubQueryBatch)
        subqueries = completion.subqueries[:n]
        self.logger.info("subquery_generation_completed", generated=len(subqueries))
        return subqueries


def _build_task(clarify: ClarifyResult) -> str:
    if clarify.verification:
        return clarify.verification
    if clarify.question:
        return clarify.question
    if clarify.rubrics:
        return "Research task guided by these rubrics: " + "; ".join(
            rubric.text for rubric in clarify.rubrics
        )
    return "Research the user's request thoroughly."


def _build_context(clarify: ClarifyResult, recall: KnowledgeRecall) -> str:
    rubric_lines = [f"- {rubric.text} (weight={rubric.weight})" for rubric in clarify.rubrics]
    gap_lines = [f"- {gap.topic}: {gap.reason}" for gap in recall.gaps]
    known_fact_lines = [f"- {fact}" for fact in recall.known_facts]

    return "\n".join(
        [
            f"Recommended research mode: {clarify.mode.value}",
            "Rubrics:",
            "\n".join(rubric_lines) if rubric_lines else "- None provided",
            "Known facts from pre-recall:",
            "\n".join(known_fact_lines) if known_fact_lines else "- None provided",
            "Known gaps from pre-recall:",
            "\n".join(gap_lines) if gap_lines else "- None provided",
        ]
    )
