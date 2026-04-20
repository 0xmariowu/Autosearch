# Self-written, plan v2.3 § 2 + § 13.5 M7
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import structlog

from autosearch.core.evidence import retrieve_for_section, split_all_evidence
from autosearch.core.models import (
    Evidence,
    EvidenceSnippet,
    OutlineNode,
    ResearchTurn,
    Rubric,
    Section,
)
from autosearch.llm.client import LLMClient
from autosearch.synthesis.citation import (
    CitationRenderer,
    apply_to_prose,
    scrub_invalid_inline_citations,
)
from autosearch.synthesis.outline import draft_outline, refine_outline
from autosearch.synthesis.section import SectionWriter

_INLINE_CITATION_RE = re.compile(r"\[(\d+)\]")
_EMPTY_SECTION_FALLBACK = "No evidence was available for this section."


@dataclass(frozen=True)
class Report:
    title: str
    outline: OutlineNode
    sections: list[Section]
    content: str
    ref_table: dict[int, Evidence]
    markdown: str


class ReportSynthesizer:
    SECTION_TOP_K = 15

    def __init__(
        self,
        section_writer: SectionWriter | None = None,
        citation_renderer: CitationRenderer | None = None,
    ) -> None:
        self.section_writer = section_writer or SectionWriter()
        self.citation_renderer = citation_renderer or CitationRenderer()
        self.logger = structlog.get_logger(__name__).bind(component="report_synthesizer")

    async def synthesize(
        self,
        query: str,
        evidences: list[Evidence],
        rubrics: list[Rubric] | None,
        client: LLMClient,
        *,
        research_trace: list[ResearchTurn] | list[dict] | None = None,
    ) -> Report:
        rubrics = rubrics or []
        normalized_research_trace = research_trace or []
        self.logger.info(
            "report_synthesis_started",
            query=query,
            evidences=len(evidences),
            rubrics=len(rubrics),
            research_turns=len(normalized_research_trace),
        )

        draft = await draft_outline(query, client)
        outline = await refine_outline(query, draft, normalized_research_trace, client)
        all_snippets = split_all_evidence(evidences)
        snippet_ref_table = _build_snippet_ref_table(all_snippets, evidences)
        snippet_ids = {
            _snippet_identity(snippet): index for index, snippet in enumerate(all_snippets, start=1)
        }

        sections: list[Section] = []
        for node in outline.walk_leaves():
            if not node.heading.strip():
                continue
            section_query = _section_query_for_node(node)
            selected = retrieve_for_section(
                section_query,
                all_snippets,
                top_k=self.SECTION_TOP_K,
            )
            self.logger.info(
                "section_retrieval",
                heading=node.heading,
                section_query=section_query,
                snippets_selected=len(selected),
            )
            section = await self.section_writer.write_section_from_snippets(
                node=node,
                snippets=selected,
                topic=query,
                client=client,
            )
            section = _rewrite_section_to_global_snippet_ids(
                section=section,
                selected=selected,
                snippet_ids=snippet_ids,
            )
            if not section.content.strip():
                section = section.model_copy(
                    update={"content": _EMPTY_SECTION_FALLBACK, "ref_ids": []}
                )
            self.logger.info(
                "section_writer",
                heading=section.heading,
                ref_ids_count=len(section.ref_ids),
            )
            sections.append(section)

        if not sections:
            sections = [
                Section(
                    heading=query.strip() or "Overview",
                    content=_EMPTY_SECTION_FALLBACK,
                    ref_ids=[],
                )
            ]

        remapped_sections, remapped_evidences = self.citation_renderer.remap_citations(
            sections,
            _ordered_snippet_evidences(all_snippets, snippet_ref_table),
        )
        content = "\n\n".join(_render_section(section) for section in remapped_sections)
        remapped_ref_table = {
            index: evidence for index, evidence in enumerate(remapped_evidences, start=1)
        }
        final_content, final_ref_table = self.citation_renderer.renumber_by_first_appearance(
            content,
            remapped_ref_table,
        )
        references = self.citation_renderer.render_references(list(final_ref_table.values()))
        sources = self.citation_renderer.sources_breakdown(list(final_ref_table.values()))
        markdown = "\n\n".join(part for part in [final_content, references, sources] if part)

        self.logger.info(
            "report_synthesized",
            sections=len(remapped_sections),
            total_evidence=len(evidences),
            total_snippets=len(all_snippets),
            ref_table_size=len(final_ref_table),
        )
        return Report(
            title=query,
            outline=outline,
            sections=remapped_sections,
            content=final_content,
            ref_table=final_ref_table,
            markdown=markdown,
        )


def _render_section(section: Section) -> str:
    if section.content:
        return f"## {section.heading}\n\n{section.content}"
    return f"## {section.heading}"


def _section_query_for_node(node: OutlineNode) -> str:
    headings = node.get_subtree_headings()
    section_query = " ".join(heading for heading in headings if heading.strip())
    return section_query or node.heading


def _rewrite_section_to_global_snippet_ids(
    *,
    section: Section,
    selected: list[EvidenceSnippet],
    snippet_ids: dict[tuple[str, int, str, str], int],
) -> Section:
    if not selected:
        return section.model_copy(update={"content": "", "ref_ids": []})

    scrubbed_content = scrub_invalid_inline_citations(section.content, valid_ids=section.ref_ids)
    local_to_global = {
        local_index: snippet_ids[_snippet_identity(snippet)]
        for local_index, snippet in enumerate(selected, start=1)
    }

    def replacer(match: re.Match[str]) -> str:
        local_ref_id = int(match.group(1))
        global_ref_id = local_to_global.get(local_ref_id)
        if global_ref_id is None:
            return ""
        return f"[{global_ref_id}]"

    rewritten_content = apply_to_prose(
        scrubbed_content,
        lambda text: _INLINE_CITATION_RE.sub(replacer, text),
    )
    rewritten_content = apply_to_prose(rewritten_content, _normalize_citation_spacing)
    rewritten_ref_ids = [
        local_to_global[ref_id] for ref_id in section.ref_ids if ref_id in local_to_global
    ]

    return section.model_copy(
        update={
            "content": rewritten_content.strip(),
            "ref_ids": _dedup_ints(rewritten_ref_ids),
        }
    )


def _ordered_snippet_evidences(
    snippets: list[EvidenceSnippet],
    snippet_ref_table: dict[int, Evidence],
) -> list[Evidence]:
    return [snippet_ref_table[index] for index in range(1, len(snippets) + 1)]


def _build_snippet_ref_table(
    snippets: list[EvidenceSnippet],
    evidences: list[Evidence],
) -> dict[int, Evidence]:
    evidence_by_id = {_evidence_lookup_key(evidence): evidence for evidence in evidences}
    fallback_fetched_at = evidences[0].fetched_at if evidences else None

    ref_table: dict[int, Evidence] = {}
    for index, snippet in enumerate(snippets, start=1):
        evidence = evidence_by_id.get(snippet.evidence_id)
        if evidence is None:
            evidence = Evidence(
                url=snippet.source_url,
                title=snippet.source_title or "Untitled",
                snippet=snippet.text,
                content=snippet.text,
                source_channel="unknown",
                fetched_at=fallback_fetched_at or _fallback_timestamp(),
            )
        ref_table[index] = evidence
    return ref_table


def _evidence_lookup_key(evidence: Evidence) -> str:
    if evidence.url:
        return evidence.url
    preview = (evidence.content or evidence.snippet or "")[:100]
    payload = f"{evidence.title}\n{preview}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _snippet_identity(snippet: EvidenceSnippet) -> tuple[str, int, str, str]:
    return (
        snippet.evidence_id,
        snippet.offset,
        snippet.source_url,
        snippet.text,
    )


def _dedup_ints(values: list[int]) -> list[int]:
    seen: set[int] = set()
    deduped: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _normalize_citation_spacing(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([,.])", r"\1", text)
    text = re.sub(r"[ \t]+(?=\n)", "", text)
    text = re.sub(r"[ \t]+$", "", text)
    return text


def _fallback_timestamp():
    from datetime import UTC, datetime

    return datetime.now(UTC)
