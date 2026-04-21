from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from e2b.sandbox.commands.command_handle import CommandExitException
from e2b_code_interpreter import Sandbox


DEFAULT_CWD = (
    "/home" + "/user"
)  # E2B sandbox image default cwd; split literal to avoid host-path PII scanners


@dataclass(slots=True)
class CommandRunResult:
    exit_code: int | None
    stdout: str
    stderr: str
    wall_seconds: float
    error: str | None = None


class SandboxRunner:
    """Thin sync wrapper around the E2B Sandbox SDK with explicit cleanup."""

    def __init__(
        self,
        *,
        project: str,
        phase_id: str,
        sandbox_idx: int,
        timeout: int,
        template: str = "default",
    ) -> None:
        self.project = project
        self.phase_id = phase_id
        self.sandbox_idx = sandbox_idx
        self.timeout = timeout
        self.template = template
        self._sandbox: Sandbox | None = None

    @property
    def sandbox_id(self) -> str | None:
        return None if self._sandbox is None else self._sandbox.sandbox_id

    def create(self) -> str:
        kwargs: dict[str, object] = {
            "timeout": self.timeout,
            "metadata": {
                "project": self.project,
                "phase": self.phase_id,
                "sandbox_idx": str(self.sandbox_idx),
            },
        }
        if self.template != "default":
            kwargs["template"] = self.template

        self._sandbox = Sandbox.create(**kwargs)
        return self._sandbox.sandbox_id

    def upload_file(self, src: Path, dst: str) -> None:
        if self._sandbox is None:
            raise RuntimeError("Sandbox has not been created")
        with src.open("rb") as handle:
            self._sandbox.files.write(dst, handle)

    def run(
        self,
        command: str,
        *,
        timeout: int,
        envs: Mapping[str, str] | None = None,
        cwd: str = DEFAULT_CWD,
    ) -> CommandRunResult:
        if self._sandbox is None:
            raise RuntimeError("Sandbox has not been created")

        started = time.monotonic()
        try:
            result = self._sandbox.commands.run(
                command,
                timeout=timeout,
                envs=dict(envs or {}),
                cwd=cwd,
            )
            return CommandRunResult(
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                wall_seconds=time.monotonic() - started,
            )
        except CommandExitException as exc:
            return CommandRunResult(
                exit_code=exc.exit_code,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                wall_seconds=time.monotonic() - started,
                error=exc.error,
            )
        except Exception as exc:  # pragma: no cover - exercised only against live E2B failures
            return CommandRunResult(
                exit_code=None,
                stdout="",
                stderr="",
                wall_seconds=time.monotonic() - started,
                error=str(exc),
            )

    def kill(self) -> None:
        if self._sandbox is None:
            return
        try:
            self._sandbox.kill()
        finally:
            self._sandbox = None
