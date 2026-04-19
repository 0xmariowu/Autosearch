# Source: storm/knowledge_storm/storm_wiki/modules/outline_generation.py:L128-L167 (adapted)
import structlog
from pydantic import BaseModel, Field

from autosearch.core.models import Evidence
from autosearch.llm.client import LLMClient
from autosearch.skills.prompts import load_prompt

OUTLINE_PROMPT = load_prompt("m7_outline")


class OutlineResponse(BaseModel):
    headings: list[str] = Field(default_factory=list)


class OutlineGenerator:
    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="outline_generator")

    async def outline(
        self,
        query: str,
        evidences: list[Evidence],
        client: LLMClient,
    ) -> list[str]:
        self.logger.info(
            "outline_generation_started",
            query=query,
            evidences=len(evidences),
        )
        prompt = OUTLINE_PROMPT.format(
            query=query,
            evidence_context=_format_evidence(evidences),
        )
        response = await client.complete(prompt, OutlineResponse)
        headings = _normalize_headings(response.headings)
        if not headings:
            headings = ["Overview"]
        self.logger.info("outline_generation_completed", headings=len(headings))
        return headings


def _normalize_headings(headings: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for heading in headings:
        cleaned = heading.strip().lstrip("#").strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def _format_evidence(evidences: list[Evidence]) -> str:
    if not evidences:
        return "- No evidence collected"
    return "\n".join(
        f"- {evidence.title} ({evidence.source_channel}) — {evidence.url}"
        for evidence in evidences[:20]
    )
