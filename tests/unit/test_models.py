# Self-written, plan v2.3 § 13.5
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from autosearch.core.models import (
    ClarifyRequest,
    ClarifyResult,
    Evidence,
    FetchedPage,
    Gap,
    KnowledgeRecall,
    LinkRef,
    MediaRef,
    Rubric,
    SearchMode,
    Section,
    SubQuery,
    TableData,
)

FIXED_TIME = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)


def _fetched_page_with_all_fields() -> FetchedPage:
    return FetchedPage(
        url="https://example.com/article",
        status_code=200,
        fetched_at=FIXED_TIME,
        html="<html><body><h1>Title</h1></body></html>",
        cleaned_html="<article><h1>Title</h1></article>",
        markdown="# Title\n\nBody",
        links=[
            LinkRef(
                href="https://example.com/internal",
                text="Read more",
                internal=True,
            ),
            LinkRef(
                href="https://external.example.org",
                text="External source",
            ),
        ],
        metadata={
            "title": "Example Title",
            "og:title": "Example OG Title",
            "description": "Example description",
            "author": "Author Name",
            "published_at": "2026-04-17T12:00:00+00:00",
        },
        tables=[
            TableData(
                headers=["Name", "Value"],
                rows=[
                    {"Name": "foo", "Value": "1"},
                    {"Name": "bar", "Value": "2"},
                ],
            )
        ],
        media=[
            MediaRef(src="https://example.com/image.png", alt="Diagram"),
            MediaRef(
                src="https://example.com/video.mp4",
                alt="Demo",
                kind="video",
            ),
        ],
    )


def test_fetched_page_minimum_fields_roundtrip() -> None:
    page = FetchedPage(url="https://example.com/article", status_code=200)

    payload = page.model_dump_json()
    restored = FetchedPage.model_validate_json(payload)

    assert restored == page
    assert restored.html == ""
    assert restored.cleaned_html == ""
    assert restored.markdown == ""
    assert restored.links == []
    assert restored.metadata == {}
    assert restored.tables == []
    assert restored.media == []


def test_fetched_page_full_roundtrip() -> None:
    page = _fetched_page_with_all_fields()

    payload = page.model_dump_json()
    restored = FetchedPage.model_validate_json(payload)

    assert restored == page


def test_fetched_page_slim_removes_html_and_cleaned_html() -> None:
    page = _fetched_page_with_all_fields()

    slimmed = page.slim()

    assert slimmed.html == ""
    assert slimmed.cleaned_html == ""
    assert slimmed.markdown == page.markdown
    assert slimmed.links == page.links
    assert slimmed.metadata == page.metadata
    assert slimmed.tables == page.tables
    assert slimmed.media == page.media


def test_fetched_page_slim_preserves_other_fields() -> None:
    page = _fetched_page_with_all_fields()

    slimmed = page.slim()

    assert slimmed.url == page.url
    assert slimmed.status_code == page.status_code
    assert slimmed.fetched_at == page.fetched_at
    assert slimmed.markdown == page.markdown
    assert slimmed.links == page.links
    assert slimmed.metadata == page.metadata
    assert slimmed.tables == page.tables
    assert slimmed.media == page.media


def test_fetched_page_slim_idempotent() -> None:
    page = _fetched_page_with_all_fields()

    assert page.slim().slim() == page.slim()


def test_evidence_with_source_page() -> None:
    evidence = Evidence(
        url="https://example.com",
        title="Example",
        snippet="snippet",
        content="content",
        source_channel="web",
        fetched_at=FIXED_TIME,
        score=0.8,
        source_page=FetchedPage(
            url="https://example.com",
            status_code=200,
            fetched_at=FIXED_TIME,
            markdown="# Example",
            links=[LinkRef(href="https://example.com/about", text="About", internal=True)],
            metadata={"title": "Example"},
        ),
    )

    payload = evidence.model_dump_json()
    restored = Evidence.model_validate_json(payload)

    assert restored == evidence
    assert restored.source_page is not None
    assert restored.source_page.markdown == "# Example"


def test_evidence_without_source_page_still_valid() -> None:
    evidence = Evidence(
        url="https://example.com",
        title="Example",
        snippet="snippet",
        content="content",
        source_channel="web",
        fetched_at=FIXED_TIME,
        score=0.8,
    )

    payload = evidence.model_dump_json()
    restored = Evidence.model_validate_json(payload)

    assert restored == evidence
    assert restored.source_page is None


def test_evidence_to_slim_dict_slims_source_page() -> None:
    source_page = _fetched_page_with_all_fields()
    evidence = Evidence(
        url="https://example.com",
        title="Example",
        snippet="snippet",
        content="content",
        source_channel="web",
        fetched_at=FIXED_TIME,
        score=0.8,
        source_page=source_page,
    )

    payload = evidence.to_slim_dict()

    assert payload["source_page"]["html"] == ""
    assert payload["source_page"]["cleaned_html"] == ""
    assert payload["source_page"]["markdown"] == source_page.markdown


def test_evidence_to_slim_dict_handles_none_source_page() -> None:
    evidence = Evidence(
        url="https://example.com",
        title="Example",
        snippet="snippet",
        content="content",
        source_channel="web",
        fetched_at=FIXED_TIME,
        score=0.8,
    )

    payload = evidence.to_slim_dict()

    assert payload["source_page"] is None


def test_link_ref_internal_flag() -> None:
    link = LinkRef(href="https://example.com/about", text="About")

    assert link.internal is False


def test_table_data_roundtrip() -> None:
    table = TableData(
        headers=["Name", "Role"],
        rows=[
            {"Name": "Alice", "Role": "Maintainer"},
            {"Name": "Bob", "Role": "Reviewer"},
        ],
    )

    payload = table.model_dump_json()
    restored = TableData.model_validate_json(payload)

    assert restored == table


def test_media_ref_default_kind_image() -> None:
    media = MediaRef(src="https://example.com/image.png", alt="A screenshot")

    assert media.kind == "image"


@pytest.mark.parametrize(
    ("factory", "field_name", "field_value", "invalid_payload"),
    [
        (
            lambda: SubQuery(text="sqlite fts5 tokenizer", rationale="search strategy seed"),
            "text",
            "updated",
            {"text": None, "rationale": "search strategy seed"},
        ),
        (
            lambda: Evidence(
                url="https://example.com",
                title="Example",
                snippet="snippet",
                content="content",
                source_channel="web",
                fetched_at=FIXED_TIME,
                score=0.8,
            ),
            "title",
            "Updated",
            {
                "url": "https://example.com",
                "title": "Example",
                "snippet": "snippet",
                "content": "content",
                "source_channel": "web",
                "fetched_at": "not-a-date",
                "score": 0.8,
            },
        ),
        (
            lambda: Gap(topic="pricing", reason="needs current vendor data"),
            "reason",
            "changed",
            {"topic": "pricing", "reason": None},
        ),
        (
            lambda: Rubric(text="Includes direct source links"),
            "weight",
            2.0,
            {"text": "Includes direct source links", "weight": "high"},
        ),
        (
            lambda: Section(heading="Summary", content="Answer", ref_ids=[1, 2]),
            "heading",
            "Updated",
            {"heading": "Summary", "content": "Answer", "ref_ids": ["bad"]},
        ),
        (
            lambda: ClarifyRequest(query="best agentic search tools", mode_hint=SearchMode.FAST),
            "query",
            "updated",
            {"query": None, "mode_hint": "fast"},
        ),
        (
            lambda: ClarifyResult(
                need_clarification=False,
                verification="Starting research",
                rubrics=[Rubric(text="Uses recent sources")],
                mode=SearchMode.DEEP,
            ),
            "mode",
            SearchMode.FAST,
            {
                "need_clarification": False,
                "verification": "Starting research",
                "rubrics": ["bad"],
                "mode": "deep",
            },
        ),
        (
            lambda: KnowledgeRecall(
                known_facts=["SQLite FTS5 supports BM25 ranking"],
                gaps=[Gap(topic="Chinese tokenization", reason="needs current implementation")],
            ),
            "known_facts",
            [],
            {"known_facts": "not-a-list", "gaps": []},
        ),
    ],
)
def test_models_validate_and_are_frozen(
    factory: object,
    field_name: str,
    field_value: object,
    invalid_payload: dict[str, object],
) -> None:
    model = factory()

    assert model is not None

    with pytest.raises(ValidationError):
        setattr(model, field_name, field_value)

    with pytest.raises(ValidationError):
        type(model).model_validate(invalid_payload)


def test_search_mode_parses_valid_values() -> None:
    assert SearchMode("fast") is SearchMode.FAST
    assert SearchMode("deep") is SearchMode.DEEP
    assert SearchMode("comprehensive") is SearchMode.COMPREHENSIVE


def test_search_mode_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        SearchMode("slow")
