# Source: storm/knowledge_storm/storm_wiki/modules/article_generation.py:L136-L177 (adapted)
#
# DEPRECATED (v2 wave 3 removal target):
# This module drives M7 final-section writing inside the autosearch synthesis
# pipeline. Under v2 tool supplier architecture, runtime AI (Claude / Cursor)
# writes the final report directly from the evidence + outline autosearch
# returns — autosearch itself does not compose sections anymore. This module
# stays so the existing `autosearch research` CLI and MCP `research()` tool
# keep producing reports for backward-compat users; new code paths must NOT
# call the section writer here. When the tool-supplier entry points are
# rewritten (wave 3), delete this module along with `m7_section_write*.md`
# and `m7_outline.md` prompts.
import re

import structlog
from pydantic import BaseModel, Field

from autosearch.core.models import Evidence, EvidenceSnippet, OutlineNode, Section
from autosearch.llm.client import LLMClient

# W3.3 PR C: m7_* prompts removed from disk. Constants kept as empty strings
# so legacy imports don't crash — env-gated code paths never invoke them.
SECTION_WRITE_PROMPT = ""
SECTION_WRITE_FROM_SNIPPETS_PROMPT = ""

_MAX_SNIPPETS_PER_PROMPT = 12
_MAX_SNIPPET_EXCERPT_CHARS = 600

_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")


class _SectionWriteResponse(BaseModel):
    content: str
    ref_ids: list[int] = Field(default_factory=list)


class SectionWriter:
    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__).bind(component="section_writer")

    async def write_section_from_snippets(
        self,
        node: OutlineNode,
        snippets: list[EvidenceSnippet],
        topic: str,
        client: LLMClient,
    ) -> Section:
        prompt_snippets = snippets[:_MAX_SNIPPETS_PER_PROMPT]
        self.logger.info(
            "section_write_started",
            heading=node.heading,
            snippets=len(snippets),
            prompt_snippets=len(prompt_snippets),
        )
        if not prompt_snippets:
            self.logger.info(
                "section_write_completed",
                heading=node.heading,
                ref_ids=0,
                prompt_snippets=0,
            )
            return Section(heading=node.heading, content="", ref_ids=[])

        snippets_context, _ = _format_snippets_for_prompt(prompt_snippets)
        prompt = SECTION_WRITE_FROM_SNIPPETS_PROMPT.format(
            topic=topic,
            section_heading=node.heading,
            section_outline=_format_section_outline(node),
            snippets_context=snippets_context,
        )
        response = await client.complete(prompt, _SectionWriteResponse)
        content = _normalize_content(response.content, node.heading)
        ref_ids = _normalize_ref_ids(content, response.ref_ids, len(prompt_snippets))
        section = Section(heading=node.heading, content=content, ref_ids=ref_ids)
        self.logger.info(
            "section_write_completed",
            heading=section.heading,
            ref_ids=len(section.ref_ids),
            prompt_snippets=len(prompt_snippets),
        )
        return section

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


def _format_section_outline(node: OutlineNode) -> str:
    headings = node.get_subtree_headings()
    if not headings:
        return "- No local subsection context provided"
    return "\n".join(f"- {heading}" for heading in headings)


def _format_snippets_for_prompt(snippets: list[EvidenceSnippet]) -> tuple[str, list[str]]:
    prompt_snippets = snippets[:_MAX_SNIPPETS_PER_PROMPT]
    if not prompt_snippets:
        return "- No snippets provided", []

    formatted: list[str] = []
    url_ordered_list: list[str] = []
    for index, snippet in enumerate(prompt_snippets, start=1):
        excerpt = _truncate_excerpt(snippet.text)
        source_url = snippet.source_url or "unknown"
        formatted.append(f'[{index}] "{excerpt}" (source: {source_url})')
        url_ordered_list.append(source_url)
    return "\n".join(formatted), url_ordered_list


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


def _truncate_excerpt(text: str, limit: int = _MAX_SNIPPET_EXCERPT_CHARS) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return "(no excerpt available)"
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."
