# Self-written, plan v2.3 § 2 + § 13.5 M7
import asyncio

import structlog

from autosearch.core.models import Evidence, Rubric, Section
from autosearch.llm.client import LLMClient
from autosearch.synthesis.citation import CitationRenderer
from autosearch.synthesis.outline import OutlineGenerator
from autosearch.synthesis.section import SectionWriter


class ReportSynthesizer:
    def __init__(
        self,
        outline_generator: OutlineGenerator | None = None,
        section_writer: SectionWriter | None = None,
        citation_renderer: CitationRenderer | None = None,
    ) -> None:
        self.outline_generator = outline_generator or OutlineGenerator()
        self.section_writer = section_writer or SectionWriter()
        self.citation_renderer = citation_renderer or CitationRenderer()
        self.logger = structlog.get_logger(__name__).bind(component="report_synthesizer")

    async def synthesize(
        self,
        query: str,
        evidences: list[Evidence],
        rubrics: list[Rubric],
        client: LLMClient,
    ) -> str:
        self.logger.info(
            "report_synthesis_started",
            query=query,
            evidences=len(evidences),
            rubrics=len(rubrics),
        )
        headings = await self.outline_generator.outline(query, evidences, client)
        sections = await asyncio.gather(
            *[self.section_writer.write_section(heading, evidences, client) for heading in headings]
        )
        remapped_sections, remapped_evidences = self.citation_renderer.remap_citations(
            sections,
            evidences,
        )
        section_markdown = "\n\n".join(_render_section(section) for section in remapped_sections)
        references = self.citation_renderer.render_references(remapped_evidences)
        sources = self.citation_renderer.sources_breakdown(remapped_evidences)
        report = "\n\n".join(part for part in [section_markdown, references, sources] if part)
        self.logger.info(
            "report_synthesis_completed",
            headings=len(headings),
            sections=len(remapped_sections),
            cited_evidences=len(remapped_evidences),
        )
        return report


def _render_section(section: Section) -> str:
    if section.content:
        return f"## {section.heading}\n\n{section.content}"
    return f"## {section.heading}"
