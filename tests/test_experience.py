from __future__ import annotations

import json

from autosearch.core.experience_compact import compact
from autosearch.skills import experience


def _make_skill_root(tmp_path, monkeypatch, skill_name: str = "demo"):
    """Set up both bundled (read-only) skill_dir and runtime experience root.

    Bundled root is needed so `_find_skill_dir` can derive the skill group;
    runtime root is where `append_event` / `compact` actually write.
    Pointing both at the same path keeps test assertions straightforward.
    """
    root = tmp_path / "skills"
    skill_dir = root / "channels" / skill_name
    skill_dir.mkdir(parents=True)
    monkeypatch.setattr(experience, "_SKILLS_ROOT", root)
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(root))
    return skill_dir


def test_append_event_creates_file_and_appends_valid_json(tmp_path, monkeypatch) -> None:
    skill_dir = _make_skill_root(tmp_path, monkeypatch)

    experience.append_event("demo", {"query": "test", "outcome": "success"})

    patterns_path = skill_dir / "experience" / "patterns.jsonl"
    lines = patterns_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload == {"outcome": "success", "query": "test"}


def test_load_experience_digest_returns_none_when_missing_and_content_when_present(
    tmp_path,
    monkeypatch,
) -> None:
    skill_dir = _make_skill_root(tmp_path, monkeypatch)

    assert experience.load_experience_digest("demo") is None

    skill_dir.joinpath("experience.md").write_text("# demo experience\n", encoding="utf-8")

    assert experience.load_experience_digest("demo") == "# demo experience\n"


def test_compact_reads_events_and_writes_experience_md_with_structure(
    tmp_path,
    monkeypatch,
) -> None:
    skill_dir = _make_skill_root(tmp_path, monkeypatch)
    patterns_dir = skill_dir / "experience"
    patterns_dir.mkdir()
    patterns_path = patterns_dir / "patterns.jsonl"
    events = [
        {
            "ts": "2026-04-22T00:00:00+00:00",
            "outcome": "success",
            "winning_pattern": "brand pain recent",
            "failure_mode": "generic reviews over-return marketing",
            "good_query": "{brand} pain 2026",
        },
        {
            "ts": "2026-04-22T00:01:00+00:00",
            "outcome": "success",
            "winning_pattern": "brand pain recent",
            "failure_mode": "generic reviews over-return marketing",
            "good_query": "{brand} pain 2026",
        },
        {
            "ts": "2026-04-22T00:02:00+00:00",
            "outcome": "error",
            "winning_pattern": "brand pain recent",
            "failure_mode": "generic reviews over-return marketing",
            "good_query": "{brand} pain 2026",
        },
    ]
    patterns_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    assert compact("demo") is True

    digest = skill_dir.joinpath("experience.md").read_text(encoding="utf-8")
    assert "# demo experience" in digest
    assert "## Active Rules" in digest
    assert "brand pain recent -- seen=3, success=2" in digest
    assert "## Failure Modes" in digest
    assert "generic reviews over-return marketing -- seen=3" in digest
    assert "## Good Query Patterns" in digest
    assert "`{brand} pain 2026` -- seen=3" in digest
    assert "## Last Compacted" in digest
    assert "Last Compacted:" in digest
    assert len(digest.splitlines()) <= 120


def test_should_compact_returns_true_when_event_count_meets_threshold(
    tmp_path,
    monkeypatch,
) -> None:
    skill_dir = _make_skill_root(tmp_path, monkeypatch)
    patterns_dir = skill_dir / "experience"
    patterns_dir.mkdir()
    patterns_path = patterns_dir / "patterns.jsonl"
    patterns_path.write_text(
        json.dumps({"outcome": "success"}) + "\n" + json.dumps({"outcome": "success"}) + "\n",
        encoding="utf-8",
    )

    assert experience.should_compact("demo", new_event_count_threshold=2) is True
