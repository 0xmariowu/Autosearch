from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
E2B_SCRIPT_DIR = ROOT / "scripts" / "e2b"


def _install_e2b_stubs(monkeypatch) -> None:
    e2b_module = ModuleType("e2b")
    sandbox_module = ModuleType("e2b.sandbox")
    commands_module = ModuleType("e2b.sandbox.commands")
    command_handle_module = ModuleType("e2b.sandbox.commands.command_handle")
    interpreter_module = ModuleType("e2b_code_interpreter")

    class CommandExitException(Exception):
        exit_code = 1
        stdout = ""
        stderr = ""
        error = "stubbed command failure"

    class Sandbox:
        @classmethod
        def create(cls, **_kwargs):
            raise AssertionError("Sandbox.create should be mocked by these tests")

    command_handle_module.CommandExitException = CommandExitException
    interpreter_module.Sandbox = Sandbox

    monkeypatch.setitem(sys.modules, "e2b", e2b_module)
    monkeypatch.setitem(sys.modules, "e2b.sandbox", sandbox_module)
    monkeypatch.setitem(sys.modules, "e2b.sandbox.commands", commands_module)
    monkeypatch.setitem(
        sys.modules,
        "e2b.sandbox.commands.command_handle",
        command_handle_module,
    )
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", interpreter_module)


def _load_run_validation(monkeypatch):
    _install_e2b_stubs(monkeypatch)
    monkeypatch.syspath_prepend(str(E2B_SCRIPT_DIR))
    sys.modules.pop("run_validation", None)
    return importlib.import_module("run_validation")


def _patch_successful_run(monkeypatch, run_validation):
    phase = run_validation.PhaseSpec(
        id="smoke",
        timeout=1,
        parallel=1,
        tasks=[run_validation.TaskSpec(id="noop", cmd="true")],
    )
    output_dirs: list[Path] = []

    def fake_execute_phase(**kwargs):
        output_dirs.append(kwargs["output_dir"])
        return {
            "phase": kwargs["phase"].id,
            "parallel": 1,
            "timeout": 1,
            "template": "default",
            "wall_seconds": 0.0,
            "passed": 1,
            "failed": 0,
            "sandboxes": [],
        }

    monkeypatch.setattr(run_validation, "load_matrix", lambda _path: SimpleNamespace(phases=[phase]))
    monkeypatch.setattr(run_validation, "load_secrets", lambda _path: {})
    monkeypatch.setattr(run_validation, "execute_phase", fake_execute_phase)
    return output_dirs


def _run_main(monkeypatch, run_validation, matrix_path: Path, output_dir: Path, *extra: str) -> int:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_validation.py",
            "--project",
            "autosearch-test",
            "--matrix",
            str(matrix_path),
            "--secrets",
            str(matrix_path.parent / "secrets.env"),
            "--output",
            str(output_dir),
            "--parallel",
            "1",
            *extra,
        ],
    )
    return run_validation.main()


def _matrix_path(tmp_path: Path) -> Path:
    matrix_path = tmp_path / "matrix.yaml"
    matrix_path.write_text("phases: {}\n", encoding="utf-8")
    return matrix_path


def test_default_does_not_delete_existing(tmp_path, monkeypatch) -> None:
    run_validation = _load_run_validation(monkeypatch)
    output_dir = tmp_path / "validation-output"
    output_dir.mkdir()
    marker = output_dir / "marker.txt"
    marker.write_text("keep me", encoding="utf-8")
    matrix_path = _matrix_path(tmp_path)
    output_dirs = _patch_successful_run(monkeypatch, run_validation)

    assert _run_main(monkeypatch, run_validation, matrix_path, output_dir) == 0

    assert marker.read_text(encoding="utf-8") == "keep me"
    assert len(output_dirs) == 1
    assert output_dirs[0].parent == output_dir
    assert output_dirs[0].name.startswith("run-")


def test_clean_output_flag_required_for_delete(tmp_path, monkeypatch) -> None:
    run_validation = _load_run_validation(monkeypatch)
    reports_root = tmp_path / "reports"
    output_dir = reports_root / "validation-output"
    output_dir.mkdir(parents=True)
    marker = output_dir / "marker.txt"
    marker.write_text("keep me", encoding="utf-8")
    matrix_path = _matrix_path(tmp_path)
    output_dirs = _patch_successful_run(monkeypatch, run_validation)
    monkeypatch.setattr(run_validation, "get_reports_root", lambda: reports_root, raising=False)

    assert _run_main(monkeypatch, run_validation, matrix_path, output_dir) == 0
    assert marker.read_text(encoding="utf-8") == "keep me"

    marker.write_text("delete me", encoding="utf-8")
    assert (
        _run_main(monkeypatch, run_validation, matrix_path, output_dir, "--clean-output")
        == 0
    )

    assert not marker.exists()
    assert output_dir.exists()
    assert len(output_dirs) == 2
    assert output_dirs[-1].parent == output_dir
    assert output_dirs[-1].name.startswith("run-")


def test_output_outside_reports_root_rejected(tmp_path, monkeypatch, capsys) -> None:
    run_validation = _load_run_validation(monkeypatch)
    reports_root = tmp_path / "reports"
    reports_root.mkdir()
    output_dir = tmp_path / "outside"
    output_dir.mkdir()
    marker = output_dir / "marker.txt"
    marker.write_text("keep me", encoding="utf-8")
    matrix_path = _matrix_path(tmp_path)
    output_dirs = _patch_successful_run(monkeypatch, run_validation)
    monkeypatch.setattr(run_validation, "get_reports_root", lambda: reports_root, raising=False)

    assert (
        _run_main(monkeypatch, run_validation, matrix_path, output_dir, "--clean-output")
        == 2
    )

    assert marker.read_text(encoding="utf-8") == "keep me"
    assert output_dirs == []
    assert "outside repo reports" in capsys.readouterr().err


def test_symlink_escape_rejected(tmp_path, monkeypatch, capsys) -> None:
    run_validation = _load_run_validation(monkeypatch)
    reports_root = tmp_path / "reports"
    reports_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker.txt"
    marker.write_text("keep me", encoding="utf-8")
    output_link = reports_root / "escape"
    output_link.symlink_to(outside, target_is_directory=True)
    matrix_path = _matrix_path(tmp_path)
    output_dirs = _patch_successful_run(monkeypatch, run_validation)
    monkeypatch.setattr(run_validation, "get_reports_root", lambda: reports_root, raising=False)

    assert (
        _run_main(monkeypatch, run_validation, matrix_path, output_link, "--clean-output")
        == 2
    )

    assert marker.read_text(encoding="utf-8") == "keep me"
    assert output_dirs == []
    assert "outside repo reports" in capsys.readouterr().err


def test_reports_root_symlink_resolved_consistently(tmp_path, monkeypatch) -> None:
    run_validation = _load_run_validation(monkeypatch)
    real_reports_root = tmp_path / "real-reports"
    real_reports_root.mkdir()
    reports_root_link = tmp_path / "reports-link"
    reports_root_link.symlink_to(real_reports_root, target_is_directory=True)
    output_dir = reports_root_link / "validation-output"
    output_dir.mkdir()
    marker = output_dir / "marker.txt"
    marker.write_text("delete me", encoding="utf-8")
    matrix_path = _matrix_path(tmp_path)
    output_dirs = _patch_successful_run(monkeypatch, run_validation)
    monkeypatch.setattr(
        run_validation,
        "get_reports_root",
        lambda: reports_root_link,
        raising=False,
    )

    assert (
        _run_main(monkeypatch, run_validation, matrix_path, output_dir, "--clean-output")
        == 0
    )

    assert not marker.exists()
    assert len(output_dirs) == 1
    assert output_dirs[0].resolve().is_relative_to(real_reports_root.resolve())
