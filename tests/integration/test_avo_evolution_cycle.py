"""G6: AVO Self-Evolution Tests (CLAUDE.md Rule 22).

Tests the full 6-step evolution cycle:
  a) baseline score
  b) agent-initiated skill modification (experience.md / patterns.jsonl)
  c) re-score showing improvement (rationale now contains active rules)
  d) git commit on improvement  ← contract test only (no actual git ops in unit test)
  e) git revert on regression   ← contract test only
  f) pattern written to state

All tests are mock-based. Marked @pytest.mark.avo @pytest.mark.slow.
Run manually: pytest tests/integration/test_avo_evolution_cycle.py -m avo -v
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from autosearch.core.experience_compact import compact
from autosearch.core.models import Evidence, SubQuery
from autosearch.skills import experience as exp_mod
from autosearch.skills.experience import append_event, load_experience_digest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ev(url: str, title: str, ch: str = "arxiv", score: float = 0.8) -> Evidence:
    return Evidence(
        url=url,
        title=title,
        snippet=".",
        source_channel=ch,
        fetched_at=datetime.now(UTC),
        score=score,
    )


def _setup_skill_dir(tmp_path: Path, channel: str, monkeypatch) -> Path:
    skill_dir = tmp_path / "channels" / channel
    skill_dir.mkdir(parents=True)
    monkeypatch.setattr(exp_mod, "_SKILLS_ROOT", tmp_path)
    return skill_dir


def _write_events(channel: str, n: int, winning_pattern: str = "use specific terms") -> None:
    """Append n success events with a winning pattern."""
    for i in range(n):
        append_event(
            channel,
            {
                "skill": channel,
                "query": f"query_{i}",
                "outcome": "success",
                "count_returned": 7,
                "count_total": 10,
                "winning_pattern": winning_pattern,
                "ts": datetime.now(UTC).isoformat(),
            },
        )


# ── Step a: Baseline ──────────────────────────────────────────────────────────


@pytest.mark.avo
def test_baseline_rationale_has_no_experience(tmp_path, monkeypatch):
    """(a) Baseline: fresh channel has no experience.md → rationale unchanged."""
    skill_dir = _setup_skill_dir(tmp_path, "arxiv", monkeypatch)
    assert not (skill_dir / "experience.md").exists()
    digest = load_experience_digest("arxiv")
    assert digest is None, "No experience.md → digest must be None"


# ── Step b: Skill modification ────────────────────────────────────────────────


@pytest.mark.avo
def test_pattern_written_to_state_after_search(tmp_path, monkeypatch):
    """(b) Agent-initiated: append_event writes winning pattern to patterns.jsonl."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)
    pattern_text = "include arxiv category filter cs.AI for better precision"

    append_event(
        "arxiv",
        {
            "skill": "arxiv",
            "query": "transformer attention mechanism",
            "outcome": "success",
            "count_returned": 9,
            "count_total": 10,
            "winning_pattern": pattern_text,
            "ts": datetime.now(UTC).isoformat(),
        },
    )

    patterns_path = tmp_path / "channels" / "arxiv" / "experience" / "patterns.jsonl"
    assert patterns_path.exists()
    events = [json.loads(l) for l in patterns_path.read_text().splitlines()]
    assert len(events) == 1
    assert events[0]["winning_pattern"] == pattern_text
    assert events[0]["outcome"] == "success"


@pytest.mark.avo
def test_multiple_patterns_accumulate_in_order(tmp_path, monkeypatch):
    """(b) Multiple events accumulate append-only — order preserved."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)
    patterns = ["pattern A", "pattern B", "pattern C"]
    for p in patterns:
        append_event(
            "arxiv",
            {
                "skill": "arxiv",
                "query": "test",
                "outcome": "success",
                "count_returned": 5,
                "count_total": 10,
                "winning_pattern": p,
                "ts": datetime.now(UTC).isoformat(),
            },
        )

    lines = (
        (tmp_path / "channels" / "arxiv" / "experience" / "patterns.jsonl").read_text().splitlines()
    )
    written = [json.loads(l)["winning_pattern"] for l in lines]
    assert written == patterns, "Patterns must be in insertion order"


@pytest.mark.avo
def test_failure_events_recorded_with_error_outcome(tmp_path, monkeypatch):
    """(b) Failed searches are also recorded — outcome='error'."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)
    append_event(
        "arxiv",
        {
            "skill": "arxiv",
            "query": "bad query",
            "outcome": "error",
            "count_returned": 0,
            "count_total": 0,
            "ts": datetime.now(UTC).isoformat(),
        },
    )

    lines = (
        (tmp_path / "channels" / "arxiv" / "experience" / "patterns.jsonl").read_text().splitlines()
    )
    assert json.loads(lines[0])["outcome"] == "error"


# ── Step c: Re-score (rationale improvement) ─────────────────────────────────


@pytest.mark.avo
def test_compact_promotes_patterns_to_active_rules(tmp_path, monkeypatch):
    """(c) After compact, experience.md has Active Rules containing winning pattern."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)
    winning = "use cs.AI category filter for machine learning papers"

    # Need seen≥3, success≥2 to promote (per compact logic)
    for i in range(5):
        append_event(
            "arxiv",
            {
                "skill": "arxiv",
                "query": f"q{i}",
                "outcome": "success",
                "count_returned": 8,
                "count_total": 10,
                "winning_pattern": winning,
                "ts": datetime.now(UTC).isoformat(),
            },
        )

    compact("arxiv")

    exp_md = tmp_path / "channels" / "arxiv" / "experience.md"
    assert exp_md.exists()
    content = exp_md.read_text()
    assert "Active Rules" in content
    assert winning in content, f"Winning pattern must appear in Active Rules:\n{content}"


@pytest.mark.avo
def test_experience_digest_injected_into_rationale_after_compact(tmp_path, monkeypatch):
    """(c) Re-score: after compact, rationale now contains Active Rule text."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)
    unique_rule = "ARXIV_EVOLUTION_TEST_RULE_XYZ"

    # Write 5 events so compact promotes the pattern
    for i in range(5):
        append_event(
            "arxiv",
            {
                "skill": "arxiv",
                "query": f"q{i}",
                "outcome": "success",
                "count_returned": 8,
                "count_total": 10,
                "winning_pattern": unique_rule,
                "ts": datetime.now(UTC).isoformat(),
            },
        )
    compact("arxiv")

    # Now load_experience_digest should return text containing the rule
    digest = load_experience_digest("arxiv")
    assert digest is not None, "digest must exist after compact"
    assert unique_rule in digest, f"Active rule must appear in digest:\n{digest}"


@pytest.mark.avo
@pytest.mark.asyncio
async def test_rationale_contains_digest_text(tmp_path, monkeypatch):
    """(c) run_channel rationale must contain experience.md text after compact."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)
    unique_rule = "PREFER_RECENT_2024_PAPERS_FOR_ARXIV"

    for i in range(5):
        append_event(
            "arxiv",
            {
                "skill": "arxiv",
                "query": f"q{i}",
                "outcome": "success",
                "count_returned": 9,
                "count_total": 10,
                "winning_pattern": unique_rule,
                "ts": datetime.now(UTC).isoformat(),
            },
        )
    compact("arxiv")

    captured = []

    class _TrackingArxiv:
        name = "arxiv"
        languages = ["en"]

        async def search(self, q: SubQuery) -> list[Evidence]:
            captured.append(q.rationale)
            return [_ev("https://arxiv.org/abs/2401.00001", "Test", "arxiv")]

    monkeypatch.setenv("AUTOSEARCH_LLM_MODE", "dummy")
    with (
        patch("autosearch.mcp.server._build_channels", return_value=[_TrackingArxiv()]),
        patch("autosearch.mcp.server.Clarifier"),
        patch("autosearch.mcp.server.LLMClient"),
    ):
        from autosearch.mcp.server import create_server

        server = create_server()
        await server._tool_manager.call_tool(
            "run_channel",
            {"channel_name": "arxiv", "query": "LLM survey", "rationale": "research"},
        )

    assert captured, "Channel must have been called"
    assert unique_rule in captured[0], (
        f"Expected Active Rule '{unique_rule}' in rationale, got:\n{captured[0]}"
    )
    assert "[Experience Digest]" in captured[0]


# ── Step d/e: commit / revert contracts ──────────────────────────────────────


@pytest.mark.avo
def test_evolution_commit_contract_documented():
    """(d/e) Contract: SKILL.md changes go through git commit; regressions get git revert.

    This is a documentation contract test — verifies that CLAUDE.md rule 17
    exists and mentions both git commit and git revert for skill changes.
    """
    claude_md = Path(__file__).parents[2] / "CLAUDE.md"
    if not claude_md.exists():
        claude_md = Path.home() / "CLAUDE.md"

    content = claude_md.read_text()
    assert "git commit" in content, "CLAUDE.md must document git commit for skill changes"
    assert "git revert" in content, "CLAUDE.md must document git revert for regressions"


# ── Step e: Regression — bad pattern does NOT promote ────────────────────────


@pytest.mark.avo
def test_bad_pattern_not_promoted_without_threshold(tmp_path, monkeypatch):
    """(e) Regression prevention: a pattern seen only once is NOT promoted to Active Rules."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)
    bad_pattern = "THIS_SHOULD_NOT_PROMOTE_single_occurrence"

    # Only 1 event — below seen≥3 threshold
    append_event(
        "arxiv",
        {
            "skill": "arxiv",
            "query": "q0",
            "outcome": "success",
            "count_returned": 10,
            "count_total": 10,
            "winning_pattern": bad_pattern,
            "ts": datetime.now(UTC).isoformat(),
        },
    )
    compact("arxiv")

    exp_md = tmp_path / "channels" / "arxiv" / "experience.md"
    if exp_md.exists():
        content = exp_md.read_text()
        assert bad_pattern not in content, (
            "Single-occurrence pattern must NOT be promoted to Active Rules"
        )


@pytest.mark.avo
def test_error_outcome_does_not_promote_to_active_rules(tmp_path, monkeypatch):
    """(e) Error events never promote patterns — only successes promote."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)
    error_pattern = "THIS_COMES_FROM_FAILED_SEARCHES"

    # 5 error events
    for i in range(5):
        append_event(
            "arxiv",
            {
                "skill": "arxiv",
                "query": f"q{i}",
                "outcome": "error",
                "count_returned": 0,
                "count_total": 0,
                "winning_pattern": error_pattern,
                "ts": datetime.now(UTC).isoformat(),
            },
        )
    compact("arxiv")

    exp_md = tmp_path / "channels" / "arxiv" / "experience.md"
    if exp_md.exists():
        content = exp_md.read_text()
        # Error patterns go to Failure Modes, not Active Rules
        lines = content.splitlines()
        active_section = False
        for line in lines:
            if "## Active Rules" in line:
                active_section = True
            if active_section and "## " in line and "Active Rules" not in line:
                active_section = False
            if active_section and error_pattern in line:
                pytest.fail(f"Error pattern must not appear in Active Rules: {line}")


# ── Step f: State integrity ───────────────────────────────────────────────────


@pytest.mark.avo
def test_patterns_jsonl_is_append_only(tmp_path, monkeypatch):
    """(f) patterns.jsonl is append-only — existing entries survive multiple runs."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)

    append_event(
        "arxiv",
        {
            "skill": "arxiv",
            "query": "first",
            "outcome": "success",
            "count_returned": 5,
            "count_total": 10,
            "ts": datetime.now(UTC).isoformat(),
        },
    )

    first_content = (tmp_path / "channels" / "arxiv" / "experience" / "patterns.jsonl").read_text()

    append_event(
        "arxiv",
        {
            "skill": "arxiv",
            "query": "second",
            "outcome": "success",
            "count_returned": 8,
            "count_total": 10,
            "ts": datetime.now(UTC).isoformat(),
        },
    )

    second_content = (tmp_path / "channels" / "arxiv" / "experience" / "patterns.jsonl").read_text()

    assert second_content.startswith(first_content), (
        "patterns.jsonl must be append-only — first event must survive second append"
    )
    assert second_content.count("\n") > first_content.count("\n")


@pytest.mark.avo
def test_experience_md_respects_120_line_limit(tmp_path, monkeypatch):
    """(f) experience.md after compact must never exceed 120 lines."""
    _setup_skill_dir(tmp_path, "arxiv", monkeypatch)

    # Write 50 events with 50 different patterns to stress-test compaction
    for i in range(50):
        pattern = f"winning_pattern_{i:03d}_details_about_query_strategy"
        for j in range(3):  # ensure seen≥3 for each
            append_event(
                "arxiv",
                {
                    "skill": "arxiv",
                    "query": f"q{i}_{j}",
                    "outcome": "success",
                    "count_returned": 8,
                    "count_total": 10,
                    "winning_pattern": pattern,
                    "ts": datetime.now(UTC).isoformat(),
                },
            )

    compact("arxiv")

    exp_md = tmp_path / "channels" / "arxiv" / "experience.md"
    assert exp_md.exists()
    line_count = len(exp_md.read_text().splitlines())
    assert line_count <= 120, f"experience.md must be <= 120 lines, got {line_count}"


@pytest.mark.avo
def test_full_evolution_cycle(tmp_path, monkeypatch):
    """(f) Full cycle: no experience → events → compact → Active Rule in digest → injected in rationale."""
    skill_dir = _setup_skill_dir(tmp_path, "dblp", monkeypatch)
    rule = "DBLP_EVOLUTION_FULL_CYCLE_RULE"

    # Step a: no digest
    assert load_experience_digest("dblp") is None

    # Step b: write events
    for i in range(5):
        append_event(
            "dblp",
            {
                "skill": "dblp",
                "query": f"query_{i}",
                "outcome": "success",
                "count_returned": 7,
                "count_total": 10,
                "winning_pattern": rule,
                "ts": datetime.now(UTC).isoformat(),
            },
        )

    patterns_path = skill_dir / "experience" / "patterns.jsonl"
    assert patterns_path.exists()
    assert len(patterns_path.read_text().splitlines()) == 5

    # Step c: compact → Active Rules
    compact("dblp")
    digest = load_experience_digest("dblp")
    assert digest is not None
    assert rule in digest

    # Step f: state is complete
    exp_md = skill_dir / "experience.md"
    assert exp_md.exists()
    assert len(exp_md.read_text().splitlines()) <= 120
    assert "Active Rules" in exp_md.read_text()
