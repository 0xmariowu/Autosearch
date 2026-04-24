from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.e2b import run_comprehensive_tests as runner
from scripts.e2b.scenarios import k_avo_evolution


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_no_llm_help_mentions_k5_real_judge() -> None:
    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/e2b/run_comprehensive_tests.py",
            "--help",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "K5" in result.stdout
    assert "OpenRouter" in result.stdout


def test_https_remote_url_accepts_github_ssh_url() -> None:
    assert (
        runner._https_remote_url("ssh://git@github.com/0xmariowu/Autosearch.git")
        == "https://github.com/0xmariowu/Autosearch.git"
    )


def test_collect_source_ref_warns_for_unpushed_branch(tmp_path, monkeypatch, capsys) -> None:
    bare = tmp_path / "origin.git"
    work = tmp_path / "work"
    _git(tmp_path, "init", "--bare", str(bare))
    _git(tmp_path, "clone", str(bare), str(work))
    _git(work, "config", "user.name", "AutoSearch Test")
    _git(work, "config", "user.email", "agent@example.com")
    (work / "README.md").write_text("seed\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-m", "chore: seed")
    _git(work, "push", "origin", "HEAD:main")
    _git(work, "checkout", "-b", "local-only")

    monkeypatch.setattr(runner, "ROOT", work)
    monkeypatch.delenv("AUTOSEARCH_E2B_REF", raising=False)
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)

    source = runner._collect_source_ref_env()

    assert source["AUTOSEARCH_E2B_REF"] == "local-only"
    assert "not found on origin" in capsys.readouterr().err


def test_k5_clone_error_summary_includes_step_output() -> None:
    summary = k_avo_evolution._format_process_failure(
        "git clone/fetch",
        stdout="fatal: couldn't find remote ref local-only\n",
        stderr="",
    )

    assert "git clone/fetch failed" in summary
    assert "remote ref local-only" in summary


def test_openrouter_model_slug_is_canonical_across_e2b_scenarios() -> None:
    for path in (REPO_ROOT / "scripts" / "e2b" / "scenarios").glob("*.py"):
        assert "anthropic/claude-haiku-4-5" not in path.read_text(encoding="utf-8")


def test_k5_trial_script_handles_openrouter_failures_without_throwing() -> None:
    source = Path(k_avo_evolution.__file__).read_text(encoding="utf-8")

    assert "response.status_code" in source
    assert "asyncio.sleep" in source
    assert "malformed OpenRouter response" in source
    assert "revised_score > baseline_score" not in source


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
