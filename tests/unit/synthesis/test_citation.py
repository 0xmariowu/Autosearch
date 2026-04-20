# Self-written, plan v2.3 § 13.5
from datetime import datetime

from autosearch.core.models import Evidence, Section
from autosearch.synthesis.citation import (
    CitationRenderer,
    renumber_by_first_appearance,
    scrub_invalid_inline_citations,
)

NOW = datetime(2026, 4, 20, 12, 0, 0)


def make_evidence(url: str, title: str, source_channel: str) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        content="Detailed evidence body for synthesis.",
        source_channel=source_channel,
        fetched_at=NOW,
    )


def test_scrub_removes_unknown_markers() -> None:
    content = "Foo [1] bar [99] baz [2]"

    scrubbed = scrub_invalid_inline_citations(content, valid_ids={1, 2})

    assert scrubbed == "Foo [1] bar baz [2]"


def test_scrub_preserves_known_markers() -> None:
    content = "[1] [2] [3]"

    scrubbed = scrub_invalid_inline_citations(content, valid_ids={1, 2, 3})

    assert scrubbed == content


def test_scrub_collapses_double_spaces_after_deletion() -> None:
    scrubbed = scrub_invalid_inline_citations("a [99] b", valid_ids={1, 2})

    assert scrubbed == "a b"


def test_scrub_empty_valid_ids_removes_all() -> None:
    scrubbed = scrub_invalid_inline_citations("a [1] b [2]", valid_ids=set())

    assert scrubbed == "a b"


def test_scrub_preserves_newlines() -> None:
    scrubbed = scrub_invalid_inline_citations("a\n[99]\nb", valid_ids=set())

    assert scrubbed == "a\n\nb"


def test_scrub_multi_digit_ids() -> None:
    assert scrub_invalid_inline_citations("[12]", valid_ids={12}) == "[12]"
    assert scrub_invalid_inline_citations("[12]", valid_ids={1, 2}) == ""


def test_scrub_handles_adjacent_markers() -> None:
    scrubbed = scrub_invalid_inline_citations("[1][99][2]", valid_ids={1, 2})

    assert scrubbed == "[1][2]"


def test_scrub_handles_content_without_markers() -> None:
    content = "plain text"

    scrubbed = scrub_invalid_inline_citations(content, valid_ids={1, 2, 3})

    assert scrubbed == content


def test_scrub_preserves_bracket_digit_in_fenced_code() -> None:
    content = "Prose [1] here [99].\n```python\narr[1]\narr[99]\n```\nMore [2]."

    scrubbed = scrub_invalid_inline_citations(content, valid_ids={1, 2})

    assert scrubbed == "Prose [1] here.\n```python\narr[1]\narr[99]\n```\nMore [2]."


def test_scrub_preserves_bracket_digit_in_inline_code() -> None:
    content = "Use `arr[5]` to access [1]."

    scrubbed = scrub_invalid_inline_citations(content, valid_ids={1})

    assert scrubbed == content


def test_renumber_by_first_appearance_basic() -> None:
    content, ref_table = renumber_by_first_appearance(
        "[5] text [2] more [5]",
        {2: "ref2", 5: "ref5", 7: "ref7"},
    )

    assert content == "[1] text [2] more [1]"
    assert ref_table == {1: "ref5", 2: "ref2"}


def test_renumber_preserves_unused_refs_absence() -> None:
    content, ref_table = renumber_by_first_appearance(
        "Only [2] is cited.",
        {2: "ref2", 5: "ref5"},
    )

    assert content == "Only [1] is cited."
    assert ref_table == {1: "ref2"}


def test_renumber_stable_across_reorder() -> None:
    once_content, once_ref_table = renumber_by_first_appearance(
        "[5] text [2] more [5]",
        {2: "ref2", 5: "ref5"},
    )

    twice_content, twice_ref_table = renumber_by_first_appearance(
        once_content,
        once_ref_table,
    )

    assert twice_content == once_content
    assert twice_ref_table == once_ref_table


def test_renumber_empty_content_returns_empty_table() -> None:
    content, ref_table = renumber_by_first_appearance(
        "",
        {2: "ref2", 5: "ref5"},
    )

    assert content == ""
    assert ref_table == {}


def test_renumber_preserves_code_blocks() -> None:
    content, ref_table = renumber_by_first_appearance(
        "[5] first.\n```\ntest[5]test\n```\n[2] second.",
        {2: "b", 5: "a"},
    )

    assert content == "[1] first.\n```\ntest[5]test\n```\n[2] second."
    assert ref_table == {1: "a", 2: "b"}


def test_renumber_preserves_inline_code() -> None:
    content, ref_table = renumber_by_first_appearance(
        "See [5] and `x[5]`.",
        {5: "a"},
    )

    assert content == "See [1] and `x[5]`."
    assert ref_table == {1: "a"}


def test_renderer_scrubs_before_remap() -> None:
    renderer = CitationRenderer()
    evidences = [
        make_evidence("https://example.com/shared", "Shared source", "web"),
        make_evidence("https://example.com/unique", "Unique source", "web"),
        make_evidence("https://example.com/shared", "Shared source duplicate", "web"),
    ]
    sections = [
        Section(heading="Findings", content="Alpha [3] extra [99] text.", ref_ids=[3]),
        Section(heading="Background", content="Beta [2][42].", ref_ids=[2]),
    ]

    remapped_sections, remapped_evidences = renderer.remap_citations(sections, evidences)

    assert sections[0].content == "Alpha [3] extra [99] text."
    assert [evidence.url for evidence in remapped_evidences] == [
        "https://example.com/shared",
        "https://example.com/unique",
    ]
    assert remapped_sections[0].content == "Alpha [1] extra text."
    assert remapped_sections[0].ref_ids == [1]
    assert remapped_sections[1].content == "Beta [2]."
    assert remapped_sections[1].ref_ids == [2]
