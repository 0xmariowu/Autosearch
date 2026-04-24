"""Guard rail: runtime experience writes must NEVER touch the installed package tree.

Without this contract a deployed wheel becomes "dirty" the moment an MCP host
calls run_channel — patterns.jsonl gets written into site-packages, causing
read-only-FS failures, build artifact pollution, and cross-user data leaks
on shared installs.
"""

from __future__ import annotations

from pathlib import Path

from autosearch.core.experience_compact import compact
from autosearch.skills import experience as exp_mod


def _bundled_arxiv_dir() -> Path:
    return exp_mod._SKILLS_ROOT / "channels" / "arxiv"


def test_append_event_writes_to_runtime_root_not_package(monkeypatch, tmp_path):
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(runtime_root))

    bundled = _bundled_arxiv_dir()
    bundled_patterns = bundled / "experience" / "patterns.jsonl"
    bundled_size_before = bundled_patterns.stat().st_size if bundled_patterns.exists() else None

    exp_mod.append_event("arxiv", {"query": "isolation test", "outcome": "success"})

    runtime_patterns = runtime_root / "channels" / "arxiv" / "experience" / "patterns.jsonl"
    assert runtime_patterns.exists(), "event must land under the runtime root"
    body = runtime_patterns.read_text(encoding="utf-8")
    assert "isolation test" in body

    if bundled_size_before is None:
        assert not bundled_patterns.exists(), (
            "append_event must not create patterns.jsonl in the installed package tree"
        )
    else:
        assert bundled_patterns.stat().st_size == bundled_size_before, (
            "append_event must not modify the bundled patterns.jsonl"
        )


def test_compact_writes_digest_to_runtime_root_not_package(monkeypatch, tmp_path):
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(runtime_root))

    runtime_patterns = runtime_root / "channels" / "arxiv" / "experience" / "patterns.jsonl"
    runtime_patterns.parent.mkdir(parents=True)
    runtime_patterns.write_text(
        '{"ts": "2026-04-22T00:00:00+00:00", "outcome": "success", '
        '"winning_pattern": "site:arxiv.org abstract", "good_query": "rag eval"}\n' * 4,
        encoding="utf-8",
    )

    bundled_digest = _bundled_arxiv_dir() / "experience.md"
    bundled_text_before = (
        bundled_digest.read_text(encoding="utf-8") if bundled_digest.exists() else None
    )

    assert compact("arxiv") is True

    runtime_digest = runtime_root / "channels" / "arxiv" / "experience.md"
    assert runtime_digest.exists(), "compact() must write the digest under the runtime root"

    if bundled_text_before is None:
        assert not bundled_digest.exists(), (
            "compact() must not create experience.md inside the installed package"
        )
    else:
        assert bundled_digest.read_text(encoding="utf-8") == bundled_text_before, (
            "compact() must not modify the bundled experience.md seed"
        )


def test_load_digest_falls_back_to_bundled_seed(monkeypatch, tmp_path):
    """When the user has no compacted digest yet, callers should still get the
    seed digest shipped with the package so the agent has prior knowledge."""
    monkeypatch.setenv("AUTOSEARCH_EXPERIENCE_DIR", str(tmp_path / "empty-runtime"))

    digest = exp_mod.load_experience_digest("arxiv")
    bundled = _bundled_arxiv_dir() / "experience.md"
    if bundled.exists():
        assert digest == bundled.read_text(encoding="utf-8")
    else:
        assert digest is None
