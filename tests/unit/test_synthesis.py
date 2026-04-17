# Self-written, plan v2.3 § 13.5
import re
from datetime import datetime

from pydantic import BaseModel

from autosearch.core.models import Evidence, Rubric, Section
from autosearch.synthesis.citation import CitationRenderer
from autosearch.synthesis.outline import OutlineResponse
from autosearch.synthesis.report import ReportSynthesizer

NOW = datetime(2026, 4, 17, 12, 0, 0)


class DummyClient:
    def __init__(self) -> None:
        self.calls = 0
        self.prompts: list[str] = []

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.calls += 1
        self.prompts.append(prompt)
        if response_model is OutlineResponse:
            payload = {"headings": ["Overview"]}
        else:
            payload = {"content": "Research summary with inline support [1].", "ref_ids": [1]}
        return response_model.model_validate(payload)


def make_evidence(url: str, title: str, source_channel: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        content="Detailed evidence body for synthesis.",
        source_channel=source_channel,
        fetched_at=NOW,
    )


async def test_report_synthesizer_outputs_sections_references_and_sources() -> None:
    client = DummyClient()
    evidences = [make_evidence("https://example.com/one", "Source One", "web")]
    rubrics = [Rubric(text="Uses cited evidence")]

    report = await ReportSynthesizer().synthesize(
        "Compare search tooling",
        evidences,
        rubrics,
        client,
    )

    assert "## Overview" in report
    assert "## References" in report
    assert re.search(r"\[1\].*https://example.com/one", report)
    assert "## Sources" in report
    assert "| Platform | Count |" in report
    assert "| web | 1 |" in report


def test_remap_citations_collapses_duplicate_urls_and_renumbers_refs() -> None:
    renderer = CitationRenderer()
    evidences = [
        make_evidence("https://example.com/shared", "Shared source", "web"),
        make_evidence("https://example.com/shared", "Shared source duplicate", "web"),
        make_evidence("https://example.com/unique", "Unique source", "reddit"),
    ]
    sections = [
        Section(heading="Findings", content="Alpha [2] and beta [3].", ref_ids=[2, 3]),
        Section(heading="Background", content="Gamma [1].", ref_ids=[1]),
    ]

    remapped_sections, remapped_evidences = renderer.remap_citations(sections, evidences)

    assert [evidence.url for evidence in remapped_evidences] == [
        "https://example.com/shared",
        "https://example.com/unique",
    ]
    assert remapped_sections[0].content == "Alpha [1] and beta [2]."
    assert remapped_sections[0].ref_ids == [1, 2]
    assert remapped_sections[1].content == "Gamma [1]."
    assert remapped_sections[1].ref_ids == [1]
