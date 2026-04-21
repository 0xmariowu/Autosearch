"""Guard the m7 section-write prompt against regressing its content-substance
rules. Prior art in the gpt-researcher project (`prompts.py` lines 298 /
317 / 622) shows the three rules every serious synthesizer prompt enforces.
Losing any of them would reopen the 0/68 pairwise-judge shutout we saw on
2026-04-21 against native-Claude reports.
"""

from __future__ import annotations

from pathlib import Path


PROMPT = (
    Path(__file__).resolve().parents[2]
    / "autosearch"
    / "skills"
    / "prompts"
    / "m7_section_write_v2.md"
)


def test_prompt_bans_generic_conclusions():
    body = PROMPT.read_text(encoding="utf-8").lower()
    assert "not defer to general" in body, (
        "m7 prompt must retain the anti-boilerplate rule (gpt-researcher line 298)"
    )


def test_prompt_requires_concrete_specifics():
    body = PROMPT.read_text(encoding="utf-8").lower()
    assert "concrete specifics" in body or "concrete, specific" in body, (
        "m7 prompt must require concrete specifics when snippets carry them"
    )
    # Spot-check the enumerated identifier list so a drive-by rewrite doesn't quietly
    # drop all the named anchors.
    for anchor in ("error codes", "benchmark", "issue"):
        assert anchor in body, f"m7 prompt must enumerate `{anchor}` as an example identifier"


def test_prompt_bans_repetition():
    body = PROMPT.read_text(encoding="utf-8").lower()
    assert "not repeat" in body, (
        "m7 prompt must retain the no-repetition rule (gpt-researcher line 622)"
    )
