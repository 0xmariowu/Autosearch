from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _load_pre_release_check() -> ModuleType:
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "validate" / "pre_release_check.py"
    module_name = "_pre_release_check_under_test"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


CHECK = _load_pre_release_check()


def _write_stats(
    tmp_path: Path,
    run_name: str,
    *,
    commit_sha: str | None,
    win_rate: float = 0.60,
    generated_at: str = "2026-04-25T00:00:00Z",
) -> Path:
    path = tmp_path / "reports" / run_name / "judge" / "stats.json"
    path.parent.mkdir(parents=True)
    stats: dict[str, object] = {
        "total": 10,
        "a_win_rate": win_rate,
        "generated_at": generated_at,
    }
    if commit_sha is not None:
        stats["commit_sha"] = commit_sha
    path.write_text(json.dumps(stats), encoding="utf-8")
    return path


def _mock_git_head(monkeypatch, head: str = "head-sha") -> None:
    def fake_run(cmd, **kwargs):
        assert cmd == ["git", "rev-parse", "HEAD"]
        return SimpleNamespace(returncode=0, stdout=f"{head}\n", stderr="")

    monkeypatch.setattr(CHECK.subprocess, "run", fake_run)


def _mock_gh_prs(monkeypatch, prs: list[dict[str, object]]) -> None:
    def fake_run(cmd, **kwargs):
        assert cmd == ["gh", "pr", "list", "--state", "open", "--json", "number,title,labels"]
        return SimpleNamespace(returncode=0, stdout=json.dumps(prs), stderr="")

    monkeypatch.setattr(CHECK.subprocess, "run", fake_run)


def test_gate12_stats_matching_commit_pass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(CHECK, "ROOT", tmp_path)
    _mock_git_head(monkeypatch)
    _write_stats(tmp_path, "matching", commit_sha="head-sha")

    ok, msg = CHECK._check_gate12_bench()

    assert ok is True
    assert "win_rate=60.0%" in msg


def test_gate12_stats_mismatched_commit_fail_stale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(CHECK, "ROOT", tmp_path)
    _mock_git_head(monkeypatch)
    _write_stats(tmp_path, "stale", commit_sha="old-sha")

    ok, msg = CHECK._check_gate12_bench()

    assert ok is False
    assert "Gate 12 stale" in msg
    assert "old-sha" in msg
    assert "head-sha" in msg


def test_gate12_no_stats_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(CHECK, "ROOT", tmp_path)

    ok, msg = CHECK._check_gate12_bench()

    assert ok is False
    assert "no Gate 12 bench results found" in msg


def test_gate12_allow_stale_passes_mismatch_with_warning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(CHECK, "ROOT", tmp_path)
    _mock_git_head(monkeypatch)
    _write_stats(tmp_path, "stale", commit_sha="old-sha")

    ok, msg = CHECK._check_gate12_bench(allow_stale=True)

    assert ok is True
    assert "WARNING: Gate 12 stale" in msg


def test_allow_stale_gate12_cli_flag_is_wired(monkeypatch) -> None:
    seen: dict[str, bool] = {}

    monkeypatch.setattr(CHECK, "_check_version_consistency", lambda: (True, "ok"))
    monkeypatch.setattr(CHECK, "_check_skill_format", lambda: (True, "ok"))
    monkeypatch.setattr(CHECK, "_check_experience_dirs", lambda: (True, "ok"))
    monkeypatch.setattr(CHECK, "_check_mcp_tools", lambda: (True, "ok"))
    monkeypatch.setattr(CHECK, "_check_open_prs", lambda: (True, "ok"))
    monkeypatch.setattr(CHECK, "_check_git_clean", lambda: (True, "ok"))

    def fake_gate12(*, allow_stale: bool = False):
        seen["allow_stale"] = allow_stale
        return True, "ok"

    monkeypatch.setattr(CHECK, "_check_gate12_bench", fake_gate12)

    assert CHECK.main(["--allow-stale-gate12"]) == 0
    assert seen == {"allow_stale": True}


def test_gate12_prefers_latest_matching_head(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(CHECK, "ROOT", tmp_path)
    _mock_git_head(monkeypatch)
    _write_stats(
        tmp_path,
        "newer-stale",
        commit_sha="old-sha",
        generated_at="2026-04-25T02:00:00Z",
    )
    _write_stats(
        tmp_path,
        "older-matching",
        commit_sha="head-sha",
        generated_at="2026-04-25T01:00:00Z",
    )

    ok, msg = CHECK._check_gate12_bench()

    assert ok is True
    assert "from older-matching" in msg


def test_open_pr_with_release_blocker_label_fails(monkeypatch) -> None:
    _mock_gh_prs(
        monkeypatch,
        [
            {
                "number": 379,
                "title": "must fix",
                "labels": [{"name": "release-blocker"}],
            }
        ],
    )

    ok, msg = CHECK._check_open_prs()

    assert ok is False
    assert "1 open PRs (1 release-blockers)" in msg
    assert "#379" in msg


def test_open_pr_without_release_blocker_label_passes(monkeypatch) -> None:
    _mock_gh_prs(
        monkeypatch,
        [
            {
                "number": 321,
                "title": "external contribution",
                "labels": [{"name": "external"}],
            }
        ],
    )

    ok, msg = CHECK._check_open_prs()

    assert ok is True
    assert msg == "1 open PRs (0 release-blockers)"


def test_zero_open_prs_passes(monkeypatch) -> None:
    _mock_gh_prs(monkeypatch, [])

    ok, msg = CHECK._check_open_prs()

    assert ok is True
    assert msg == "0 open PRs (0 release-blockers)"
