from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate" / "check_version_uniqueness.py"
VERSION = "2026.04.25.7"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_version_uniqueness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "autosearch"\nversion = "{VERSION}"\n',
        encoding="utf-8",
    )
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test User")
    _run_git(repo, "add", "pyproject.toml")
    _run_git(repo, "commit", "-m", "initial")
    return repo


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


@pytest.fixture()
def module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    loaded = _load_module()
    monkeypatch.setattr(loaded, "ROOT", _make_repo(tmp_path))
    return loaded


def test_version_not_in_local_tags_and_not_on_pypi_exits_zero(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse({"releases": {"2026.04.25.6": []}}),
    )

    assert module.main(["--mode=full"]) == module.OK
    captured = capsys.readouterr()
    assert f"OK: version {VERSION} not yet claimed" in captured.out


def test_local_tag_pointing_to_head_is_allowed(module: ModuleType) -> None:
    _run_git(module.ROOT, "tag", f"v{VERSION}")

    assert module.main(["--mode=local"]) == module.OK


def test_local_tag_pointing_to_other_commit_fails(
    module: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _run_git(module.ROOT, "tag", f"v{VERSION}")
    (module.ROOT / "later.txt").write_text("later\n", encoding="utf-8")
    _run_git(module.ROOT, "add", "later.txt")
    _run_git(module.ROOT, "commit", "-m", "later")

    assert module.main(["--mode=local"]) == module.CONFLICT
    captured = capsys.readouterr()
    assert "points to" in captured.err
    assert "not current HEAD" in captured.err


def test_pypi_existing_version_fails(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse({"releases": {"2026.4.25.7": []}}),
    )

    assert module.main(["--mode=pypi"]) == module.CONFLICT
    captured = capsys.readouterr()
    assert f"FAIL: version {VERSION} already on PyPI" in captured.err


def test_local_mode_skips_network(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_urlopen(*args: object, **kwargs: object) -> object:
        raise AssertionError("network should not be called")

    monkeypatch.setattr(module.urllib.request, "urlopen", fail_urlopen)

    assert module.main(["--mode=local"]) == module.OK


def test_pypi_network_failure_exits_nonzero_with_clear_message(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_urlopen(*args: object, **kwargs: object) -> object:
        raise OSError("network unavailable")

    monkeypatch.setattr(module.urllib.request, "urlopen", fail_urlopen)

    assert module.main(["--mode=pypi"]) == module.UNVERIFIED
    captured = capsys.readouterr()
    assert f"WARN: could not verify version {VERSION} on PyPI" in captured.err
    assert "network unavailable" in captured.err
