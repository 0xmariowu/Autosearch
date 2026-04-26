from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path

from scripts.e2b.lib import packing


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> None:
    _run_git(tmp_path, "init")
    _run_git(tmp_path, "config", "user.email", "test@example.com")
    _run_git(tmp_path, "config", "user.name", "Test User")


def test_pack_includes_only_tracked_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    (tmp_path / "a.py").write_text("print(1)", encoding="utf-8")
    _run_git(tmp_path, "add", "a.py")
    _run_git(tmp_path, "commit", "-m", "Add tracked Python file")

    (tmp_path / ".gitignore").write_text("b.env", encoding="utf-8")
    _run_git(tmp_path, "add", ".gitignore")
    _run_git(tmp_path, "commit", "-m", "Ignore env file")

    (tmp_path / "b.env").write_text("SECRET=xxx", encoding="utf-8")

    tarball = packing.pack_directory(tmp_path, tmp_path / "out.tar.gz")

    with tarfile.open(tarball, "r:gz") as archive:
        names = archive.getnames()

    assert "a.py" in names
    assert "b.env" not in names


def test_pack_aborts_on_secret(tmp_path: Path, monkeypatch) -> None:
    """If gitleaks finds a secret in the tracked source dir, packing must abort."""
    import shutil as _shutil

    if _shutil.which("gitleaks") is None:
        import pytest

        pytest.skip("gitleaks not installed in this environment")

    _init_repo(tmp_path)

    (tmp_path / "ok.py").write_text("print(0)", encoding="utf-8")
    # Build a synthetic AWS-key-shaped string at runtime (split prefix/suffix)
    # so the test source itself does not trigger the autosearch repo's gitleaks
    # PR-diff scan. The combined value still triggers gitleaks default
    # aws-access-key rule when written to leak.py.
    fake_aws_key = "AKIA" + "Z7Q2JHXMVRE5KFL2"
    (tmp_path / "leak.py").write_text(f'AWS_ACCESS_KEY = "{fake_aws_key}"\n', encoding="utf-8")
    _run_git(tmp_path, "add", "-A")
    _run_git(tmp_path, "commit", "-m", "Add file with leaked AWS access key")

    import pytest

    with pytest.raises(RuntimeError, match="secret-scan"):
        packing.pack_directory(tmp_path, tmp_path / "out.tar.gz")


def test_pack_excludes_denylist_even_if_tracked(tmp_path: Path) -> None:
    """Even if a sensitive file (.env) is force-added to git, packing must skip it."""
    _init_repo(tmp_path)

    (tmp_path / "ok.py").write_text("print(2)", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=xxx", encoding="utf-8")
    (tmp_path / "deploy.key").write_text("-----PRIVATE----", encoding="utf-8")
    (tmp_path / "experience").mkdir()
    (tmp_path / "experience" / "log.md").write_text("private", encoding="utf-8")

    # Force add everything, including would-be-ignored .env / .key.
    _run_git(tmp_path, "add", "-A", "-f")
    _run_git(tmp_path, "commit", "-m", "Force add tracked + sensitive files")

    tarball = packing.pack_directory(tmp_path, tmp_path / "out.tar.gz")

    with tarfile.open(tarball, "r:gz") as archive:
        names = archive.getnames()

    assert "ok.py" in names
    assert ".env" not in names
    assert "deploy.key" not in names
    assert "experience/log.md" not in names
