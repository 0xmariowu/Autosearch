# Source: storm/knowledge_storm/storm_wiki/modules/article_generation.py:L136-L177 (adapted)
import re

import structlog
from pydantic import BaseModel, Field

from autosearch.core.models import Evidence, Section
from autosearch.llm.client import LLMClient
from autosearch.skills.prompts import load_prompt

SECTION_WRITE_PROMPT = load_prompt("m7_section_write")

_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")


class _SectionWriteResponse(BaseModel):
    content: str
    ref_ids: list[int] = Field(default_factory=list)


class SectionWriter:
    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="section_writer")

    async def write_section(
        self,
        heading: str,
        evidences: list[Evidence],
        client: LLMClient,
    ) -> Section:
        self.logger.info(
            "section_write_started",
            heading=heading,
            evidences=len(evidences),
        )
        prompt = SECTION_WRITE_PROMPT.format(
            heading=heading,
            evidence_context=_format_evidence(evidences),
        )
        response = await client.complete(prompt, _SectionWriteResponse)
        content = _normalize_content(response.content, heading)
        ref_ids = _normalize_ref_ids(content, response.ref_ids, len(evidences))
        section = Section(heading=heading, content=content, ref_ids=ref_ids)
        self.logger.info(
            "section_write_completed",
            heading=heading,
            ref_ids=len(section.ref_ids),
        )
        return section


def _normalize_content(content: str, heading: str) -> str:
    lines = content.strip().splitlines()
    if not lines:
        return ""

    first_line = lines[0].strip()
    normalized_heading = heading.strip().casefold()
    normalized_first_line = first_line.lstrip("#").strip().casefold()
    if normalized_first_line == normalized_heading:
        lines = lines[1:]

    return "\n".join(lines).strip()


def _normalize_ref_ids(content: str, ref_ids: list[int], evidence_count: int) -> list[int]:
    content_ref_ids = [int(match.group(1)) for match in _INLINE_CITATION_RE.finditer(content)]
    merged_ref_ids = content_ref_ids + ref_ids

    seen: set[int] = set()
    normalized: list[int] = []
    for ref_id in merged_ref_ids:
        if ref_id < 1 or ref_id > evidence_count or ref_id in seen:
            continue
        seen.add(ref_id)
        normalized.append(ref_id)
    return normalized


def _format_evidence(evidences: list[Evidence]) -> str:
    if not evidences:
        return "- No evidence provided"

    formatted: list[str] = []
    for index, evidence in enumerate(evidences, start=1):
        body = (evidence.content or evidence.snippet or "").strip()
        excerpt = body[:600] if body else "(no summary available)"
        formatted.append(
            "\n".join(
                [
                    f"[{index}] {evidence.title}",
                    f"URL: {evidence.url}",
                    f"Channel: {evidence.source_channel}",
                    f"Excerpt: {excerpt}",
                ]
            )
        )
    return "\n\n".join(formatted)
