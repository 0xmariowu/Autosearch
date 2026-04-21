"""F510 W3 citation hardening bench.

Covers `scrub_invalid_inline_citations` + `renumber_by_first_appearance` +
`apply_to_prose` — key post-W3 citation-quality primitives.
"""

from __future__ import annotations

from autosearch.synthesis.citation import (
    apply_to_prose,
    renumber_by_first_appearance,
    scrub_invalid_inline_citations,
)


def test_scrub_removes_invalid_ids() -> None:
    content = "BM25 scores well [1]. Off-topic mention [99]. Back to BM25 [2]."
    scrubbed = scrub_invalid_inline_citations(content, valid_ids=[1, 2])
    assert "[99]" not in scrubbed
    assert "[1]" in scrubbed
    assert "[2]" in scrubbed


def test_scrub_keeps_valid_ids_intact() -> None:
    content = "[1][2][3] all here."
    scrubbed = scrub_invalid_inline_citations(content, valid_ids=[1, 2, 3])
    assert "[1]" in scrubbed
    assert "[2]" in scrubbed
    assert "[3]" in scrubbed


def test_scrub_protects_code_blocks() -> None:
    content = "Sentence [1]. \n```python\ndef fn(): return [99]\n```\nMore [2]."
    scrubbed = scrub_invalid_inline_citations(content, valid_ids=[1, 2])
    # Code block content preserved verbatim — `[99]` inside is NOT scrubbed
    assert "return [99]" in scrubbed
    # But prose [1] + [2] remain and no rogue [99] in prose
    assert "Sentence [1]." in scrubbed
    assert "More [2]." in scrubbed


def test_renumber_by_first_appearance() -> None:
    content = "First cite [5]. Second cite [3]. Third cite [5] reused. Fourth [7]."
    ref_table = {5: {"url": "a"}, 3: {"url": "b"}, 7: {"url": "c"}, 99: {"url": "nope"}}

    new_content, new_table = renumber_by_first_appearance(content, ref_table)

    # Sequential 1,2,3 assignment in order of first appearance: 5→1, 3→2, 7→3
    assert "[1]" in new_content  # formerly [5]
    assert "[2]" in new_content  # formerly [3]
    assert "[3]" in new_content  # formerly [7]
    # Reordered ref table has three entries, new-id-keyed, 99 (uncited) dropped
    assert set(new_table.keys()) == {1, 2, 3}


def test_apply_to_prose_preserves_inline_code() -> None:
    def upper_prose(text: str) -> str:
        return text.upper()

    content = "Hello `world` today."
    out = apply_to_prose(content, upper_prose)
    assert "HELLO" in out
    assert "TODAY" in out
    assert "`world`" in out  # inline code preserved verbatim
