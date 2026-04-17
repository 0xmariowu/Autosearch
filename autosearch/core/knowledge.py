# Self-written, plan v2.3 § 1 decision 16 + § 13.5
from textwrap import dedent

import structlog

from autosearch.core.models import KnowledgeRecall
from autosearch.llm.client import LLMClient

KNOWLEDGE_RECALL_PROMPT = dedent(
    """\
    You are preparing for a research task.

    User query:
    <Query>
    {query}
    </Query>

    Return only what you can state confidently without doing any search.
    Separate that from the unknowns that require research.

    Respond in valid JSON with these exact keys:
    - "known_facts": a list of concise bullet-style facts you can answer confidently now
    - "gaps": a list of objects with exact keys "topic" and "reason"

    Rules:
    - Keep known_facts factual, specific, and short
    - Do not guess, hedge, or include facts that need verification
    - Use gaps to name the missing information that should be searched next
    - An empty known_facts list is allowed
    - An empty gaps list is allowed if the query is answerable from prior knowledge
    """
).strip()


class KnowledgeRecaller:
    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="knowledge_recaller")

    async def recall(self, query: str, client: LLMClient) -> KnowledgeRecall:
        self.logger.info("knowledge_recall_started", query=query)
        prompt = KNOWLEDGE_RECALL_PROMPT.format(query=query)
        result = await client.complete(prompt, KnowledgeRecall)
        self.logger.info(
            "knowledge_recall_completed",
            known_facts=len(result.known_facts),
            gaps=len(result.gaps),
        )
        return result
