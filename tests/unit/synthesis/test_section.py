# Self-written, plan v2.3 § 13.5
from datetime import datetime

from pydantic import BaseModel

from autosearch.core.models import Evidence, EvidenceSnippet, OutlineNode
from autosearch.synthesis.section import SectionWriter

NOW = datetime(2026, 4, 20, 12, 0, 0)


class FakeLLMClient:
    def __init__(
        self,
        *,
        content: str = "Generated section [1].",
        ref_ids: list[int] | None = None,
    ) -> None:
        self.calls = 0
        self.prompts: list[str] = []
        self.content = content
        self.ref_ids = ref_ids or []

    async def complete(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        self.calls += 1
        self.prompts.append(prompt)
        payload = {"content": self.content}
        if "ref_ids" in response_model.model_fields:
            payload["ref_ids"] = self.ref_ids
        return response_model.model_validate(payload)


def make_snippet(index: int, text: str | None = None) -> EvidenceSnippet:
    return EvidenceSnippet(
        evidence_id=f"ev-{index}",
        text=text or f"Snippet text {index}",
        offset=0,
        source_url=f"https://example.com/{index}",
        source_title=f"Source {index}",
    )


def make_evidence(index: int) -> Evidence:
    return Evidence(
        url=f"https://example.com/evidence/{index}",
        title=f"Evidence {index}",
        content=f"Evidence body {index}",
        source_channel="web",
        fetched_at=NOW,
    )


async def test_write_section_from_snippets_basic() -> None:
    client = FakeLLMClient(
        content="Python async is cool [1]. BM25 is a ranking function [3].",
    )
    node = OutlineNode(heading="Overview", level=2)
    snippets = [make_snippet(1), make_snippet(2), make_snippet(3)]

    section = await SectionWriter().write_section_from_snippets(
        node=node,
        snippets=snippets,
        topic="Compare search tooling",
        client=client,
    )

    assert section.heading == "Overview"
    assert section.content == "Python async is cool [1]. BM25 is a ranking function [3]."
    assert section.ref_ids == [1, 3]


async def test_write_section_from_snippets_passes_outline_to_prompt() -> None:
    client = FakeLLMClient()
    node = OutlineNode(
        heading="Approach",
        level=2,
        children=[
            OutlineNode(heading="Retrieval", level=3),
            OutlineNode(heading="Synthesis", level=3),
        ],
    )

    await SectionWriter().write_section_from_snippets(
        node=node,
        snippets=[make_snippet(1)],
        topic="Compare search tooling",
        client=client,
    )

    prompt = client.prompts[0]
    assert "Approach" in prompt
    assert "Approach > Retrieval" in prompt
    assert "Approach > Synthesis" in prompt


async def test_write_section_from_snippets_caps_snippet_count() -> None:
    client = FakeLLMClient()
    snippets = [make_snippet(index) for index in range(1, 21)]

    await SectionWriter().write_section_from_snippets(
        node=OutlineNode(heading="Overview", level=2),
        snippets=snippets,
        topic="Compare search tooling",
        client=client,
    )

    prompt = client.prompts[0]
    assert "[12]" in prompt
    assert "[13]" not in prompt
    assert "https://example.com/12" in prompt
    assert "https://example.com/13" not in prompt


async def test_write_section_from_snippets_truncates_long_snippet_text() -> None:
    client = FakeLLMClient()
    long_text = "x" * 5000

    await SectionWriter().write_section_from_snippets(
        node=OutlineNode(heading="Overview", level=2),
        snippets=[make_snippet(1, text=long_text)],
        topic="Compare search tooling",
        client=client,
    )

    prompt = client.prompts[0]
    assert f'"{"x" * 600}..."' in prompt
    assert f'"{"x" * 601}' not in prompt


async def test_write_section_from_snippets_handles_empty_snippets() -> None:
    client = FakeLLMClient()

    section = await SectionWriter().write_section_from_snippets(
        node=OutlineNode(heading="Overview", level=2),
        snippets=[],
        topic="Compare search tooling",
        client=client,
    )

    assert section.heading == "Overview"
    assert section.content == ""
    assert section.ref_ids == []
    assert client.calls == 0


async def test_write_section_preserves_old_signature_still_works() -> None:
    client = FakeLLMClient(
        content="## Background\nLegacy section body [1].",
        ref_ids=[1],
    )

    section = await SectionWriter().write_section(
        heading="Background",
        evidences=[make_evidence(1)],
        client=client,
    )

    assert section.heading == "Background"
    assert section.content == "Legacy section body [1]."
    assert section.ref_ids == [1]
    assert client.calls == 1
