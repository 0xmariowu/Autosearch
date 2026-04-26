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


def _mock_pre_release_checks(
    monkeypatch,
    *,
    mandatory_ok: bool = True,
    advisory_ok: bool = True,
) -> None:
    """Patch the MANDATORY_CHECKS / ADVISORY_CHECKS lists with stub callables.

    Patching the module-level lists (rather than the underlying `_check_*`
    functions) is necessary because the production lists hold direct
    function references — captured at import time — so swapping a module
    attr does not change what the loop iterates over.
    """
    failing_label = "Version 4-file consistency"

    def make_mandatory_fn(label: str):
        if not mandatory_ok and label == failing_label:
            return lambda: (False, "mandatory failed")
        return lambda: (True, "mandatory passed")

    new_mandatory = [(label, make_mandatory_fn(label)) for label, _ in CHECK.MANDATORY_CHECKS]
    new_advisory = [
        (label, lambda *, allow_stale=False: (advisory_ok, "advisory result"))
        for label, _ in CHECK.ADVISORY_CHECKS
    ]

    monkeypatch.setattr(CHECK, "MANDATORY_CHECKS", new_mandatory)
    monkeypatch.setattr(CHECK, "ADVISORY_CHECKS", new_advisory)


def test_advisory_mandatory_checks_list_contains_expected_labels() -> None:
    labels = [label for label, _ in CHECK.MANDATORY_CHECKS]

    assert labels == [
        "Version 4-file consistency",
        "SKILL.md format",
        "Channel experience dirs",
        "MCP tools registered",
        "Open PR release blockers",
        "Git working tree clean",
    ]
    assert "Gate 12 bench ≥ 50%" not in labels


def test_advisory_checks_list_contains_gate12_bench() -> None:
    labels = [label for label, _ in CHECK.ADVISORY_CHECKS]

    assert labels == ["Gate 12 bench ≥ 50%"]


def test_advisory_failure_does_not_make_main_exit_nonzero(monkeypatch, capsys) -> None:
    _mock_pre_release_checks(monkeypatch, mandatory_ok=True, advisory_ok=False)

    assert CHECK.main([]) == 0
    output = capsys.readouterr().out
    assert "[WARN] [advisory] Gate 12 bench ≥ 50%" in output
    assert "MANDATORY: 6/6 passed" in output
    assert "ADVISORY: 0/1 passed" in output


def test_advisory_main_exits_nonzero_when_mandatory_fails(monkeypatch, capsys) -> None:
    _mock_pre_release_checks(monkeypatch, mandatory_ok=False, advisory_ok=True)

    assert CHECK.main([]) == 1
    output = capsys.readouterr().out
    assert "❌  [mandatory] Version 4-file consistency" in output
    assert "MANDATORY: 5/6 passed" in output
    assert "ADVISORY: 1/1 passed" in output


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

    new_mandatory = [(label, lambda: (True, "ok")) for label, _ in CHECK.MANDATORY_CHECKS]
    monkeypatch.setattr(CHECK, "MANDATORY_CHECKS", new_mandatory)

    def fake_gate12(*, allow_stale: bool = False):
        seen["allow_stale"] = allow_stale
        return True, "ok"

    monkeypatch.setattr(CHECK, "ADVISORY_CHECKS", [("Gate 12 bench ≥ 50%", fake_gate12)])

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
