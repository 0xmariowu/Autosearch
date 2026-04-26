#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

from lib.packing import pack_directory
from lib.matrix import Expectation, MatrixError, PhaseSpec, TaskSpec, UploadSpec, load_matrix
from lib.reporter import summarize_phase, write_phase_summary, write_run_summary, write_task_result
from lib.sandbox import CommandRunResult, SandboxRunner
from lib.secrets import SecretsError, build_task_env, load_secrets

DEFAULT_PARALLEL = 20
MAX_PARALLEL = 20
DEFAULT_SECRETS_PATH = Path("~/.config/ai-secrets.env").expanduser()
GLOBAL_UPLOAD_DIR = "/tmp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run validation matrices inside E2B sandboxes.")
    parser.add_argument("--project", required=True, help="Project label written into reports")
    parser.add_argument("--matrix", required=True, help="Path to the matrix YAML file")
    parser.add_argument(
        "--secrets", default=str(DEFAULT_SECRETS_PATH), help="Path to KEY=VALUE secrets env file"
    )
    parser.add_argument("--output", required=True, help="Directory where reports will be written")
    parser.add_argument(
        "--parallel", type=int, default=DEFAULT_PARALLEL, help="Default sandboxes per phase"
    )
    parser.add_argument(
        "--tarball", help="Optional tarball uploaded to every sandbox at /tmp/<filename>"
    )
    parser.add_argument(
        "--source-dir", help="Pack this directory to a temp tarball and use it as --tarball"
    )
    parser.add_argument("--phase", help="Optional CSV filter for phases to run")
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete the base output directory before creating this run's report directory",
    )
    return parser.parse_args()


def expectation_to_dict(expectation: Expectation) -> dict[str, Any]:
    return {
        "exit": expectation.exit,
        "exit_nonzero": expectation.exit_nonzero,
        "stdout_contains": expectation.stdout_contains,
        "stderr_contains": expectation.stderr_contains,
        "stdout_regex": expectation.stdout_regex,
    }


def evaluate_expectation(
    expectation: Expectation, result: CommandRunResult
) -> tuple[bool, str | None]:
    if result.error and result.exit_code is None:
        return False, f"command error: {result.error}"

    if expectation.exit_nonzero:
        if result.exit_code == 0:
            return False, "expected non-zero exit code"
    elif expectation.exit is not None and result.exit_code != expectation.exit:
        return False, f"expected exit {expectation.exit}, got {result.exit_code}"

    if expectation.stdout_contains is not None and expectation.stdout_contains not in result.stdout:
        return False, f"stdout missing substring: {expectation.stdout_contains!r}"
    if expectation.stderr_contains is not None and expectation.stderr_contains not in result.stderr:
        return False, f"stderr missing substring: {expectation.stderr_contains!r}"
    if (
        expectation.stdout_regex
        and re.search(expectation.stdout_regex, result.stdout, re.MULTILINE) is None
    ):
        return False, f"stdout missing regex: {expectation.stdout_regex!r}"

    return True, None


def warn_missing_secrets(
    *,
    console: Console,
    phase_id: str,
    sandbox_idx: int,
    task_id: str,
    missing_keys: Iterable[str],
) -> None:
    for key in missing_keys:
        console.log(
            f"[yellow]WARN[/] phase={phase_id} sandbox={sandbox_idx} task={task_id} missing secret {key}"
        )


def log_task_status(
    console: Console,
    phase_id: str,
    sandbox_idx: int,
    task_id: str,
    passed: bool,
    reason: str | None,
) -> None:
    status = "[green]PASS[/]" if passed else "[red]FAIL[/]"
    suffix = "" if reason is None else f" reason={reason}"
    console.log(f"{status} phase={phase_id} sandbox={sandbox_idx} task={task_id}{suffix}")


def build_task_result(
    *,
    task: TaskSpec,
    sandbox_id: str | None,
    sandbox_idx: int,
    run_result: CommandRunResult,
    resolved_keys: list[str],
    resolved_key_sources: dict[str, str],
    setup_env_keys_resolved: list[str],
    setup_env_key_sources: dict[str, str],
    passed: bool,
    fail_reason: str | None,
) -> dict[str, Any]:
    return {
        "id": task.id,
        "sandbox_id": sandbox_id,
        "sandbox_idx": sandbox_idx,
        "exit_code": run_result.exit_code,
        "stdout": run_result.stdout,
        "stderr": run_result.stderr,
        "wall_seconds": run_result.wall_seconds,
        "expectations": expectation_to_dict(task.expect),
        "env_keys_resolved": resolved_keys,
        "env_keys_resolved_sources": resolved_key_sources,
        "setup_env_keys_resolved": setup_env_keys_resolved,
        "setup_env_keys_resolved_sources": setup_env_key_sources,
        "passed": passed,
        "fail_reason": fail_reason,
        "error": run_result.error,
    }


def build_phase_uploads(phase: PhaseSpec, tarball: Path | None) -> list[UploadSpec]:
    uploads = list(phase.upload)
    if tarball is not None:
        uploads.insert(0, UploadSpec(src=tarball, dst=f"{GLOBAL_UPLOAD_DIR}/{tarball.name}"))
    return uploads


def run_sandbox_group(
    *,
    project: str,
    phase: PhaseSpec,
    sandbox_idx: int,
    secrets: dict[str, str],
    tarball: Path | None,
    phase_dir: Path,
    console: Console,
) -> dict[str, Any]:
    started = time.monotonic()
    setup_env, setup_resolved_keys, setup_missing_keys, setup_resolved_sources = build_task_env(
        secrets,
        phase.setup_env_keys,
        [],
    )
    runner = SandboxRunner(
        project=project,
        phase_id=phase.id,
        sandbox_idx=sandbox_idx,
        timeout=phase.timeout,
        template=phase.template,
    )
    results: list[dict[str, Any]] = []
    uploads = build_phase_uploads(phase, tarball)

    try:
        try:
            runner.create()
        except Exception as exc:
            return fail_all_tasks(
                phase=phase,
                phase_dir=phase_dir,
                console=console,
                sandbox_idx=sandbox_idx,
                sandbox_id=None,
                reason=f"sandbox create failed: {exc}",
                run_result=CommandRunResult(
                    exit_code=None, stdout="", stderr="", wall_seconds=0.0, error=str(exc)
                ),
                setup_resolved_keys=setup_resolved_keys,
                setup_resolved_sources=setup_resolved_sources,
                started=started,
            )

        try:
            for upload in uploads:
                runner.upload_file(upload.src, upload.dst)
        except Exception as exc:
            return fail_all_tasks(
                phase=phase,
                phase_dir=phase_dir,
                console=console,
                sandbox_idx=sandbox_idx,
                sandbox_id=runner.sandbox_id,
                reason=f"upload failed: {exc}",
                run_result=CommandRunResult(
                    exit_code=None, stdout="", stderr="", wall_seconds=0.0, error=str(exc)
                ),
                setup_resolved_keys=setup_resolved_keys,
                setup_resolved_sources=setup_resolved_sources,
                started=started,
            )

        if phase.setup:
            warn_missing_secrets(
                console=console,
                phase_id=phase.id,
                sandbox_idx=sandbox_idx,
                task_id="setup",
                missing_keys=setup_missing_keys,
            )
            setup_result = runner.run(phase.setup, timeout=phase.timeout, envs=setup_env)
            if setup_result.exit_code != 0 or setup_result.error:
                reason = setup_failure_reason(setup_result)
                return fail_all_tasks(
                    phase=phase,
                    phase_dir=phase_dir,
                    console=console,
                    sandbox_idx=sandbox_idx,
                    sandbox_id=runner.sandbox_id,
                    reason=reason,
                    run_result=setup_result,
                    setup_resolved_keys=setup_resolved_keys,
                    setup_resolved_sources=setup_resolved_sources,
                    started=started,
                )

        for task in phase.tasks:
            env, resolved_keys, missing_keys, resolved_sources = build_task_env(
                secrets,
                task.env_keys,
                task.unset_env,
            )
            warn_missing_secrets(
                console=console,
                phase_id=phase.id,
                sandbox_idx=sandbox_idx,
                task_id=task.id,
                missing_keys=missing_keys,
            )

            run_result = runner.run(task.cmd, timeout=task.timeout, envs=env)
            passed, fail_reason = evaluate_expectation(task.expect, run_result)
            task_result = build_task_result(
                task=task,
                sandbox_id=runner.sandbox_id,
                sandbox_idx=sandbox_idx,
                run_result=run_result,
                resolved_keys=resolved_keys,
                resolved_key_sources=resolved_sources,
                setup_env_keys_resolved=setup_resolved_keys,
                setup_env_key_sources=setup_resolved_sources,
                passed=passed,
                fail_reason=fail_reason,
            )
            write_task_result(phase_dir, task_result)
            log_task_status(console, phase.id, sandbox_idx, task.id, passed, fail_reason)
            results.append(task_result)
    finally:
        runner.kill()

    return {
        "sandbox_idx": sandbox_idx,
        "sandbox_id": results[0]["sandbox_id"] if results else runner.sandbox_id,
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "wall_seconds": round(time.monotonic() - started, 3),
        "tasks": results,
    }


def fail_all_tasks(
    *,
    phase: PhaseSpec,
    phase_dir: Path,
    console: Console,
    sandbox_idx: int,
    sandbox_id: str | None,
    reason: str,
    run_result: CommandRunResult,
    setup_resolved_keys: list[str],
    setup_resolved_sources: dict[str, str],
    started: float,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for task in phase.tasks:
        task_result = build_task_result(
            task=task,
            sandbox_id=sandbox_id,
            sandbox_idx=sandbox_idx,
            run_result=run_result,
            resolved_keys=[],
            resolved_key_sources={},
            setup_env_keys_resolved=setup_resolved_keys,
            setup_env_key_sources=setup_resolved_sources,
            passed=False,
            fail_reason=reason,
        )
        write_task_result(phase_dir, task_result)
        log_task_status(console, phase.id, sandbox_idx, task.id, False, reason)
        results.append(task_result)

    return {
        "sandbox_idx": sandbox_idx,
        "sandbox_id": sandbox_id,
        "passed": 0,
        "failed": len(results),
        "wall_seconds": round(time.monotonic() - started, 3),
        "tasks": results,
    }


def setup_failure_reason(result: CommandRunResult) -> str:
    if result.exit_code is not None:
        return f"setup failed: exit {result.exit_code}"
    if result.error:
        return f"setup failed: {result.error}"
    return "setup failed"


def execute_phase(
    *,
    project: str,
    phase: PhaseSpec,
    default_parallel: int,
    secrets: dict[str, str],
    tarball: Path | None,
    output_dir: Path,
    progress: Progress,
) -> dict[str, Any]:
    phase_parallel = min(phase.parallel or default_parallel, MAX_PARALLEL)
    phase_dir = output_dir / phase.id
    phase_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    progress_id = progress.add_task(
        f"Phase {phase.id} (0/{phase_parallel} sandboxes done)",
        total=phase_parallel,
    )

    sandbox_summaries: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=phase_parallel) as executor:
        futures = [
            executor.submit(
                run_sandbox_group,
                project=project,
                phase=phase,
                sandbox_idx=sandbox_idx,
                secrets=secrets,
                tarball=tarball,
                phase_dir=phase_dir,
                console=progress.console,
            )
            for sandbox_idx in range(1, phase_parallel + 1)
        ]

        completed = 0
        for future in as_completed(futures):
            sandbox_summaries.append(future.result())
            completed += 1
            progress.update(
                progress_id,
                completed=completed,
                description=f"Phase {phase.id} ({completed}/{phase_parallel} sandboxes done)",
            )

    phase_summary = summarize_phase(
        phase_id=phase.id,
        parallel=phase_parallel,
        timeout=phase.timeout,
        template=phase.template,
        wall_seconds=time.monotonic() - started,
        sandboxes=sorted(sandbox_summaries, key=lambda item: item["sandbox_idx"]),
    )
    write_phase_summary(phase_dir, phase_summary)
    return phase_summary


def get_reports_root() -> Path:
    return Path.cwd() / "reports"


def _path_is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return child != parent


def clean_output_dir(output_dir: Path, console: Console) -> None:
    reports_root = get_reports_root().expanduser().absolute()
    clean_target = output_dir.expanduser().absolute()
    if not _path_is_inside(clean_target, reports_root):
        raise ValueError(
            f"Refusing to clean output outside repo reports/: {clean_target} "
            f"is not inside {reports_root}"
        )

    if output_dir.exists():
        console.print(f"[yellow]WARN[/] wiping existing output directory {clean_target}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def create_run_output_dir(
    base_output_dir: Path,
    *,
    clean_output: bool,
    console: Console,
) -> Path:
    if clean_output:
        clean_output_dir(base_output_dir, console)
    else:
        base_output_dir.mkdir(parents=True, exist_ok=True)

    for _attempt in range(100):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_output_dir = base_output_dir / f"run-{timestamp}"
        try:
            run_output_dir.mkdir()
        except FileExistsError:
            time.sleep(0.001)
            continue
        return run_output_dir
    raise ValueError(f"Unable to create a unique run output directory under {base_output_dir}")


def select_phases(all_phases: list[PhaseSpec], phase_filter: str | None) -> list[PhaseSpec]:
    if not phase_filter:
        return all_phases
    wanted = {item.strip() for item in phase_filter.split(",") if item.strip()}
    return [phase for phase in all_phases if phase.id in wanted]


def validate_inputs(
    args: argparse.Namespace,
    phases: list[PhaseSpec],
    tarball: Path | None,
    source_dir: Path | None,
) -> None:
    if args.parallel <= 0:
        raise ValueError("--parallel must be a positive integer")
    if not phases:
        raise ValueError("--phase filter excluded all phases")
    if tarball is not None and source_dir is not None:
        raise ValueError("--source-dir cannot be used together with --tarball")
    if tarball is not None and not tarball.exists():
        raise ValueError(f"Tarball not found: {tarball}")
    if source_dir is not None and not source_dir.is_dir():
        raise ValueError(f"Source directory not found: {source_dir}")
    for phase in phases:
        if phase.parallel is not None and phase.parallel <= 0:
            raise ValueError(f"Phase {phase.id} parallel must be positive")
        for upload in phase.upload:
            if not upload.src.exists():
                raise ValueError(f"Upload source not found for phase {phase.id}: {upload.src}")


def maybe_pack_source_dir(source_dir: Path | None) -> Path | None:
    if source_dir is None:
        return None

    temp_tarball = tempfile.NamedTemporaryFile(prefix="e2b-source-", suffix=".tar.gz", delete=False)
    temp_tarball.close()
    return pack_directory(source_dir, Path(temp_tarball.name))


def main() -> int:
    stderr_console = Console(stderr=True, log_path=False)
    generated_tarball: Path | None = None

    try:
        args = parse_args()
        matrix_path = Path(args.matrix).expanduser().resolve()
        secrets_path = Path(args.secrets).expanduser()
        base_output_dir = Path(args.output).expanduser()
        tarball = Path(args.tarball).expanduser().resolve() if args.tarball else None
        source_dir = Path(args.source_dir).expanduser().resolve() if args.source_dir else None

        if not matrix_path.exists():
            raise ValueError(f"Matrix file not found: {matrix_path}")
        matrix = load_matrix(matrix_path)
        phases = select_phases(matrix.phases, args.phase)
        validate_inputs(args, phases, tarball, source_dir)
        generated_tarball = maybe_pack_source_dir(source_dir)
        effective_tarball = generated_tarball or tarball
        secrets = load_secrets(secrets_path)
        if "E2B_API_KEY" in secrets and "E2B_API_KEY" not in os.environ:
            os.environ["E2B_API_KEY"] = secrets["E2B_API_KEY"]

        output_dir = create_run_output_dir(
            base_output_dir,
            clean_output=args.clean_output,
            console=stderr_console,
        )

        started_at = datetime.now(timezone.utc).isoformat()
        with Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=stderr_console,
        ) as progress:
            phase_summaries = [
                execute_phase(
                    project=args.project,
                    phase=phase,
                    default_parallel=args.parallel,
                    secrets=secrets,
                    tarball=effective_tarball,
                    output_dir=output_dir,
                    progress=progress,
                )
                for phase in phases
            ]

        summary = {
            "project": args.project,
            "started_at": started_at,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "phases": phase_summaries,
        }
        write_run_summary(output_dir, summary)
        return 0 if all(phase["failed"] == 0 for phase in phase_summaries) else 1
    except (MatrixError, SecretsError, ValueError) as exc:
        stderr_console.print(f"error: {exc}")
        return 2
    except Exception as exc:  # pragma: no cover - defensive top-level guard
        stderr_console.print(f"orchestrator error: {exc}")
        return 2
    finally:
        if generated_tarball is not None and generated_tarball.exists():
            generated_tarball.unlink()


if __name__ == "__main__":
    sys.exit(main())
