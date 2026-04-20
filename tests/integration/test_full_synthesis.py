# Self-written for F306 full synthesis coverage
import re
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from autosearch.core.models import Evidence, EvidenceSnippet, Section
from autosearch.synthesis.outline import OutlineResponse
from autosearch.synthesis.report import ReportSynthesizer
import autosearch.synthesis.report as report_module

NOW = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
OUTLINE_MARKDOWN = "# Intro\n# Methods\n# Results\n# Conclusion"


class FakeLLMClient:
    def __init__(
        self,
        *,
        draft_markdown: str = OUTLINE_MARKDOWN,
        refine_markdown: str = OUTLINE_MARKDOWN,
        section_payloads: list[dict[str, object]] | None = None,
    ) -> None:
        self.draft_markdown = draft_markdown
        self.refine_markdown = refine_markdown
        self.section_payloads = list(section_payloads or [])
        self.prompts: list[str] = []
        self.response_models: list[type[BaseModel]] = []
        self.outline_calls = 0
        self.section_calls = 0

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.prompts.append(prompt)
        self.response_models.append(response_model)
        if response_model is OutlineResponse:
            self.outline_calls += 1
            markdown = self.draft_markdown if self.outline_calls == 1 else self.refine_markdown
            return response_model.model_validate({"markdown": markdown})

        payload = self.section_payloads[self.section_calls]
        self.section_calls += 1
        return response_model.model_validate(payload)


def make_evidence(index: int, *, url: str | None = None) -> Evidence:
    return Evidence(
        url=url or f"https://example.com/source-{index}",
        title=f"Source {index}",
        snippet=f"Evidence snippet {index}",
        content=(
            f"Evidence body {index} with intro methods results conclusion context and "
            f"distinct facts for section retrieval."
        ),
        source_channel="web",
        fetched_at=NOW,
    )


def make_research_trace() -> list[dict[str, object]]:
    return [
        {
            "iteration": 1,
            "batch_index": 1,
            "subqueries": ["autosearch synthesis outline retrieval"],
            "gaps": [],
            "digest_id_if_any": None,
        }
    ]


def install_retrieve_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    selections: list[list[int]],
) -> list[tuple[str, int]]:
    calls: list[tuple[str, int]] = []

    def fake_retrieve(section_query: str, snippets, *, top_k: int):
        call_index = len(calls)
        calls.append((section_query, top_k))
        selected_indexes = selections[call_index]
        return [snippets[index] for index in selected_indexes if index < len(snippets)]

    monkeypatch.setattr(report_module, "retrieve_for_section", fake_retrieve)
    return calls


def cited_numbers(content: str) -> list[int]:
    return [int(match.group(1)) for match in re.finditer(r"\[(\d+)\]", content)]


def test_report_local_to_global_rewrite_skips_code_blocks() -> None:
    section = Section(
        heading="Claim",
        content="Claim [1].\n```\nmatrix[1]\n```\nDone.",
        ref_ids=[1],
    )
    selected = [
        EvidenceSnippet(
            evidence_id="evidence-2",
            text="Second snippet",
            offset=1,
            source_url="https://example.com/2",
            source_title="Source 2",
        )
    ]
    snippet_ids = {
        report_module._snippet_identity(selected[0]): 2,
    }

    rewritten = report_module._rewrite_section_to_global_snippet_ids(
        section=section,
        selected=selected,
        snippet_ids=snippet_ids,
    )

    assert rewritten.content == "Claim [2].\n```\nmatrix[1]\n```\nDone."
    assert rewritten.ref_ids == [2]


@pytest.mark.asyncio
async def test_full_synthesis_produces_report(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeLLMClient(
        section_payloads=[
            {"content": "Intro section [1] and [2].", "ref_ids": [1, 2]},
            {"content": "Methods section [1] and [2].", "ref_ids": [1, 2]},
            {"content": "Results section [1] and [2].", "ref_ids": [1, 2]},
            {"content": "Conclusion section [1] and [2].", "ref_ids": [1, 2]},
        ]
    )
    evidences = [make_evidence(index) for index in range(1, 11)]
    install_retrieve_stub(
        monkeypatch,
        selections=[[0, 1], [2, 3], [4, 5], [6, 7]],
    )

    report = await ReportSynthesizer().synthesize(
        query="x",
        evidences=evidences,
        rubrics=[],
        client=client,
        research_trace=make_research_trace(),
    )

    assert [section.heading for section in report.sections] == [
        "Intro",
        "Methods",
        "Results",
        "Conclusion",
    ]
    assert report.content
    assert report.ref_table
    cited = cited_numbers(report.content)
    assert cited
    assert set(cited) <= set(report.ref_table)
    assert all(number >= 1 for number in cited)
    assert client.outline_calls == 2


@pytest.mark.asyncio
async def test_full_synthesis_per_section_retrieval_happens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeLLMClient(
        section_payloads=[
            {"content": "Intro [1].", "ref_ids": [1]},
            {"content": "Methods [1].", "ref_ids": [1]},
            {"content": "Results [1].", "ref_ids": [1]},
            {"content": "Conclusion [1].", "ref_ids": [1]},
        ]
    )
    evidences = [make_evidence(index) for index in range(1, 6)]
    calls = install_retrieve_stub(
        monkeypatch,
        selections=[[0], [1], [2], [3]],
    )

    report = await ReportSynthesizer().synthesize(
        query="x",
        evidences=evidences,
        rubrics=[],
        client=client,
        research_trace=make_research_trace(),
    )

    assert len(calls) == len(list(report.outline.walk_leaves()))
    assert [query for query, _ in calls] == ["Intro", "Methods", "Results", "Conclusion"]
    assert all(top_k == ReportSynthesizer.SECTION_TOP_K for _, top_k in calls)


@pytest.mark.asyncio
async def test_full_synthesis_citation_renumber_is_monotonic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeLLMClient(
        section_payloads=[
            {"content": "Intro [1] and [2].", "ref_ids": [1, 2]},
            {"content": "Methods [1] and [2].", "ref_ids": [1, 2]},
            {"content": "Results [1] and [2].", "ref_ids": [1, 2]},
            {"content": "Conclusion [1] and [2].", "ref_ids": [1, 2]},
        ]
    )
    evidences = [make_evidence(index) for index in range(1, 7)]
    install_retrieve_stub(
        monkeypatch,
        selections=[[0, 1], [1, 2], [2, 3], [3, 4]],
    )

    report = await ReportSynthesizer().synthesize(
        query="x",
        evidences=evidences,
        rubrics=[],
        client=client,
        research_trace=make_research_trace(),
    )

    first_seen: list[int] = []
    seen: set[int] = set()
    for number in cited_numbers(report.content):
        if number in seen:
            continue
        seen.add(number)
        first_seen.append(number)

    assert first_seen == list(range(1, len(first_seen) + 1))


@pytest.mark.asyncio
async def test_full_synthesis_handles_empty_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeLLMClient(section_payloads=[])
    calls = install_retrieve_stub(
        monkeypatch,
        selections=[[], [], [], []],
    )

    report = await ReportSynthesizer().synthesize(
        query="x",
        evidences=[],
        rubrics=[],
        client=client,
        research_trace=make_research_trace(),
    )

    assert report.content
    assert "No evidence was available" in report.content
    assert report.ref_table == {}
    assert client.outline_calls == 2
    assert client.section_calls == 0
    assert len(calls) == 4


@pytest.mark.asyncio
async def test_full_synthesis_uses_all_distinct_urls_in_ref_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeLLMClient(
        section_payloads=[
            {"content": "Intro [1] and [2].", "ref_ids": [1, 2]},
            {"content": "Methods [1] and [2].", "ref_ids": [1, 2]},
            {"content": "Results [1].", "ref_ids": [1]},
            {"content": "Conclusion [1].", "ref_ids": [1]},
        ]
    )
    evidences = [
        make_evidence(1, url="https://example.com/shared"),
        make_evidence(2, url="https://example.com/shared"),
        make_evidence(3, url="https://example.com/unique-a"),
        make_evidence(4, url="https://example.com/unique-b"),
    ]
    install_retrieve_stub(
        monkeypatch,
        selections=[[0, 2], [1, 3], [2], [3]],
    )

    report = await ReportSynthesizer().synthesize(
        query="x",
        evidences=evidences,
        rubrics=[],
        client=client,
        research_trace=make_research_trace(),
    )

    cited_urls = [evidence.url for evidence in report.ref_table.values()]
    assert cited_urls == [
        "https://example.com/shared",
        "https://example.com/unique-a",
        "https://example.com/unique-b",
    ]
    assert len(cited_urls) == len(set(cited_urls))
