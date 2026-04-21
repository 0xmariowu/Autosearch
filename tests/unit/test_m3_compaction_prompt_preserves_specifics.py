"""Guard the m3 evidence-compaction prompt against regressing its
preserve-specifics rules. Prior art in open_deep_research's
`compress_research_system_prompt` says "preserve all relevant information
verbatim" — the opposite of autosearch's prior "5-15 concise bullets" which
stripped identifiers judge needs (error codes, issue numbers, benchmarks).
"""

from __future__ import annotations

from pathlib import Path


PROMPT = (
    Path(__file__).resolve().parents[2]
    / "autosearch"
    / "skills"
    / "prompts"
    / "m3_evidence_compaction.md"
)


def test_prompt_does_not_cap_bullets_to_5_to_15():
    body = PROMPT.read_text(encoding="utf-8")
    assert "5 to 15 concise factual bullets" not in body, (
        "m3 compaction must NOT cap at 5-15 concise bullets; open_deep_research "
        "prior art preserves all relevant information."
    )


def test_prompt_preserves_specifics_verbatim():
    body = PROMPT.read_text(encoding="utf-8").lower()
    assert "verbatim" in body, "m3 compaction must instruct verbatim preservation"
    assert "do not" in body and ("paraphrase" in body or "summariz" in body), (
        "m3 compaction must forbid paraphrasing/summarizing"
    )


def test_prompt_enumerates_anchor_types():
    body = PROMPT.read_text(encoding="utf-8").lower()
    # Spot-check the enumerated identifier types so a drive-by rewrite
    # doesn't quietly drop the list.
    for anchor in ("error codes", "issue", "version", "benchmark"):
        assert anchor in body, (
            f"m3 compaction must name `{anchor}` as an example of a specific to preserve"
        )
