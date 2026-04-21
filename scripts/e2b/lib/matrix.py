from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class MatrixError(ValueError):
    """Raised when the matrix YAML is invalid."""


@dataclass(slots=True)
class Expectation:
    exit: int | None = 0
    exit_nonzero: bool = False
    stdout_contains: str | None = None
    stderr_contains: str | None = None
    stdout_regex: str | None = None


@dataclass(slots=True)
class TaskSpec:
    id: str
    cmd: str
    env_keys: list[str] = field(default_factory=list)
    unset_env: list[str] = field(default_factory=list)
    timeout: int = 180
    expect: Expectation = field(default_factory=Expectation)


@dataclass(slots=True)
class UploadSpec:
    src: Path
    dst: str


@dataclass(slots=True)
class PhaseSpec:
    id: str
    timeout: int
    tasks: list[TaskSpec]
    parallel: int | None = None
    template: str = "default"
    upload: list[UploadSpec] = field(default_factory=list)
    setup_env_keys: list[str] = field(default_factory=list)
    setup: str | None = None


@dataclass(slots=True)
class MatrixSpec:
    phases: list[PhaseSpec]


def load_matrix(path: Path) -> MatrixSpec:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MatrixError(f"Failed to parse matrix YAML: {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("phases"), dict) or not raw["phases"]:
        raise MatrixError("Matrix must contain a non-empty top-level 'phases' mapping")

    matrix_dir = path.parent
    phases: list[PhaseSpec] = []
    for phase_id, phase_raw in raw["phases"].items():
        phase = _as_mapping(phase_raw, f"phase {phase_id}")
        tasks_raw = phase.get("tasks")
        if not isinstance(tasks_raw, list) or not tasks_raw:
            raise MatrixError(f"Phase {phase_id} must define a non-empty tasks list")

        uploads: list[UploadSpec] = []
        upload_items = phase.get("upload", [])
        if upload_items is None:
            upload_items = []
        if not isinstance(upload_items, list):
            raise MatrixError(f"Phase {phase_id} upload must be a list")
        for item in upload_items:
            upload = _as_mapping(item, f"phase {phase_id} upload entry")
            src = Path(_as_string(upload.get("src"), f"phase {phase_id} upload src")).expanduser()
            if not src.is_absolute():
                src = (matrix_dir / src).resolve()
            uploads.append(UploadSpec(src=src, dst=_as_string(upload.get("dst"), f"phase {phase_id} upload dst")))

        tasks = [_load_task(phase_id, task_raw) for task_raw in tasks_raw]
        phases.append(
            PhaseSpec(
                id=str(phase_id),
                parallel=_as_optional_int(phase.get("parallel"), f"phase {phase_id} parallel"),
                timeout=_as_int(phase.get("timeout"), f"phase {phase_id} timeout"),
                template=_as_string(phase.get("template", "default"), f"phase {phase_id} template"),
                upload=uploads,
                setup_env_keys=_as_string_list(phase.get("setup_env_keys", []), f"phase {phase_id} setup_env_keys"),
                setup=_as_optional_string(phase.get("setup"), f"phase {phase_id} setup"),
                tasks=tasks,
            )
        )

    return MatrixSpec(phases=phases)


def _load_task(phase_id: str, task_raw: Any) -> TaskSpec:
    task = _as_mapping(task_raw, f"phase {phase_id} task")
    expect_raw = _as_mapping(task.get("expect", {}), f"phase {phase_id} task expect")
    if expect_raw.get("exit_nonzero") and "exit" in expect_raw:
        raise MatrixError(f"Task {task.get('id', '<unknown>')} in phase {phase_id} cannot set both exit and exit_nonzero")

    stdout_regex = _as_optional_match_string(expect_raw.get("stdout_regex"), "stdout_regex")
    if stdout_regex:
        try:
            re.compile(stdout_regex)
        except re.error as exc:
            raise MatrixError(
                f"Invalid stdout_regex for task {task.get('id', '<unknown>')} in phase {phase_id}: {exc}"
            ) from exc

    return TaskSpec(
        id=_as_string(task.get("id"), f"phase {phase_id} task id"),
        cmd=_as_string(task.get("cmd"), f"task {task.get('id', '<unknown>')} cmd"),
        env_keys=_as_string_list(task.get("env_keys", []), f"task {task.get('id', '<unknown>')} env_keys"),
        unset_env=_as_string_list(task.get("unset_env", []), f"task {task.get('id', '<unknown>')} unset_env"),
        timeout=_as_int(task.get("timeout", 180), f"task {task.get('id', '<unknown>')} timeout"),
        expect=Expectation(
            exit=_as_optional_exit_code(expect_raw.get("exit", 0), "expect.exit"),
            exit_nonzero=bool(expect_raw.get("exit_nonzero", False)),
            stdout_contains=_as_optional_match_string(expect_raw.get("stdout_contains"), "expect.stdout_contains"),
            stderr_contains=_as_optional_match_string(expect_raw.get("stderr_contains"), "expect.stderr_contains"),
            stdout_regex=stdout_regex,
        ),
    )


def _as_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MatrixError(f"Expected {label} to be a mapping")
    return value


def _as_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MatrixError(f"Expected {label} to be a non-empty string")
    return value


def _as_optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MatrixError(f"Expected {label} to be a string or null")
    return value


def _as_optional_match_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MatrixError(f"Expected {label} to be a string or null")
    # Empty match strings are silent no-ops: "" is contained in every string, and an
    # empty regex would also trivially match. Normalize them away at load time.
    return value or None


def _as_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MatrixError(f"Expected {label} to be a positive integer")
    return value


def _as_optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _as_int(value, label)


def _as_optional_exit_code(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MatrixError(f"Expected {label} to be a non-negative integer or null")
    return value


def _as_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise MatrixError(f"Expected {label} to be a list of strings")
    if not all(isinstance(item, str) for item in value):
        raise MatrixError(f"Expected {label} to contain only strings")
    return list(value)
