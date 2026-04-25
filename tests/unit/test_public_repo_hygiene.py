"""Tests for scripts/validate/public_repo_hygiene.py.

Per public-repo-hygiene-plan F011 S2 — covers path rules, content rules,
and allowlists. The script itself is imported via sys.path because
`scripts/validate/` is not a Python package.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "validate"))

import public_repo_hygiene as hyg  # noqa: E402


# ---------- Path rules ----------


class TestPathRules:
    def test_blocks_handoff_md(self) -> None:
        violations = hyg.check_path_rules(["HANDOFF.md"])
        assert violations == [("HANDOFF.md", 0, "tracked-handoff")]

    def test_blocks_internal_plan_dirs(self) -> None:
        files = [
            "docs/plans/foo.md",
            "docs/proposals/bar.md",
            "docs/spikes/baz.md",
            "docs/channel-hunt/qux.md",
            "docs/exec-plans/zap.md",
        ]
        violations = hyg.check_path_rules(files)
        assert len(violations) == 5
        assert all(v[2] == "tracked-internal-dir" for v in violations)

    def test_blocks_experience_jsonl(self) -> None:
        violations = hyg.check_path_rules(["autosearch/skills/foo/experience/patterns.jsonl"])
        assert violations == [
            (
                "autosearch/skills/foo/experience/patterns.jsonl",
                0,
                "tracked-experience-jsonl",
            )
        ]

    def test_blocks_private_and_handoff_md(self) -> None:
        violations = hyg.check_path_rules(["draft.private.md", "wip.handoff.md"])
        ids = [v[2] for v in violations]
        assert ids.count("tracked-private-md") == 2

    def test_blocks_reports_dir(self) -> None:
        violations = hyg.check_path_rules(["reports/run-1.txt"])
        assert ("reports/run-1.txt", 0, "tracked-reports") in [
            (v[0], v[1], v[2]) for v in violations
        ]

    def test_blocks_ds_store_at_root_and_subdir(self) -> None:
        violations = hyg.check_path_rules([".DS_Store", "subdir/.DS_Store"])
        ds_violations = [v for v in violations if v[2] == "tracked-ds-store"]
        assert len(ds_violations) == 2

    def test_clean_public_paths_pass(self) -> None:
        files = [
            "README.md",
            "README.zh.md",
            "autosearch/cli/main.py",
            "tests/unit/test_foo.py",
            "docs/install.md",
            "docs/quickstart.mdx",
            "scripts/install.sh",
            ".gitignore",
        ]
        assert hyg.check_path_rules(files) == []


# ---------- Content rules ----------


class TestContentRules:
    def test_detects_dangerous_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bad = tmp_path / "docs" / "forbidden.md"
        bad.parent.mkdir(parents=True)
        bad.write_text("Run with --dangerously-skip-permissions to skip.\n")
        monkeypatch.setattr(hyg, "REPO_ROOT", tmp_path)
        violations = hyg.check_content_rules(["docs/forbidden.md"])
        assert len(violations) == 1
        path, line_no, rule_id = violations[0]
        assert path == "docs/forbidden.md"
        assert line_no == 1
        assert rule_id == "dangerous-permission-flag"

    def test_allowlists_test_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = tmp_path / "tests" / "unit" / "test_foo.py"
        path.parent.mkdir(parents=True)
        path.write_text("# Negative test of --dangerously-skip-permissions usage\n")
        monkeypatch.setattr(hyg, "REPO_ROOT", tmp_path)
        assert hyg.check_content_rules(["tests/unit/test_foo.py"]) == []

    def test_allowlists_workflow_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / ".github" / "workflows" / "hygiene.yml"
        path.parent.mkdir(parents=True)
        path.write_text("description: dangerously-skip-permissions check\n")
        monkeypatch.setattr(hyg, "REPO_ROOT", tmp_path)
        assert hyg.check_content_rules([".github/workflows/hygiene.yml"]) == []

    def test_allowlists_husky_hook(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = tmp_path / ".husky" / "pre-commit"
        path.parent.mkdir(parents=True)
        path.write_text("grep dangerously-skip-permissions\n")
        monkeypatch.setattr(hyg, "REPO_ROOT", tmp_path)
        assert hyg.check_content_rules([".husky/pre-commit"]) == []

    def test_allowlists_gitleaks_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / ".gitleaks.toml"
        path.write_text("regex = '''dangerously-skip-permissions'''\n")
        monkeypatch.setattr(hyg, "REPO_ROOT", tmp_path)
        assert hyg.check_content_rules([".gitleaks.toml"]) == []

    def test_clean_public_doc_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = tmp_path / "README.md"
        path.write_text("# Hello\n\nNothing internal here.\n")
        monkeypatch.setattr(hyg, "REPO_ROOT", tmp_path)
        assert hyg.check_content_rules(["README.md"]) == []


# ---------- CLI entrypoint ----------


class TestEntrypoint:
    def test_help_exits_cleanly(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            hyg.main(["--help"])
        assert exc_info.value.code == 0

    def test_paths_only_skips_content_rules(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Stage one bad-content file (not on path-rule blocklist).
        path = tmp_path / "docs" / "bad.md"
        path.parent.mkdir(parents=True)
        path.write_text("dangerously-skip-permissions\n")
        monkeypatch.setattr(hyg, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(hyg, "list_tracked_files", lambda: ["docs/bad.md"])

        # With --paths-only, the content violation is skipped → exit 0.
        assert hyg.main(["--paths-only"]) == 0

        # Without --paths-only, the content violation triggers exit 1.
        assert hyg.main([]) == 1
