from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from autosearch.core.redact import redact


MAX_OUTPUT_CHARS = 10_000


def write_task_result(phase_dir: Path, result: Mapping[str, Any]) -> None:
    stem = phase_dir / f"{result['sandbox_idx']}_{result['id']}"
    _write_text(stem.with_suffix(".stdout.log"), result.get("stdout", ""))
    _write_text(stem.with_suffix(".stderr.log"), result.get("stderr", ""))

    payload = dict(result)
    payload["stdout"] = _truncate(redact(str(payload.get("stdout", ""))))
    payload["stderr"] = _truncate(redact(str(payload.get("stderr", ""))))
    if "wall_seconds" in payload:
        payload["wall_seconds"] = round(float(payload["wall_seconds"]), 3)
    _write_json(stem.with_suffix(".json"), payload)


def write_phase_summary(phase_dir: Path, summary: Mapping[str, Any]) -> None:
    _write_json(phase_dir / "summary.json", summary)


def write_run_summary(output_dir: Path, summary: Mapping[str, Any]) -> None:
    _write_json(output_dir / "summary.json", summary)
    (output_dir / "summary.md").write_text(render_summary_markdown(summary), encoding="utf-8")


def render_summary_markdown(summary: Mapping[str, Any]) -> str:
    phases = summary.get("phases", [])
    lines = [
        f"# Validation Summary: {summary['project']}",
        "",
        f"Started: {summary['started_at']}",
        f"Ended: {summary['ended_at']}",
        "",
        "| phase | passed | failed | wall_seconds |",
        "| --- | ---: | ---: | ---: |",
    ]
    for phase in phases:
        lines.append(
            f"| {phase['phase']} | {phase['passed']} | {phase['failed']} | {phase['wall_seconds']:.3f} |"
        )

    total_passed = sum(int(phase["passed"]) for phase in phases)
    total_failed = sum(int(phase["failed"]) for phase in phases)
    total_wall = sum(float(phase["wall_seconds"]) for phase in phases)
    lines.extend(
        [
            "",
            f"Total passed: {total_passed}",
            f"Total failed: {total_failed}",
            f"Total wall_seconds: {total_wall:.3f}",
            "",
        ]
    )
    return "\n".join(lines)


def json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def redacted_json_ready(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, Path):
        return redact(str(value))
    if isinstance(value, dict):
        return {key: redacted_json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redacted_json_ready(item) for item in value]
    return value


def summarize_phase(
    *,
    phase_id: str,
    parallel: int,
    timeout: int,
    template: str,
    wall_seconds: float,
    sandboxes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    passed = sum(int(sandbox["passed"]) for sandbox in sandboxes)
    failed = sum(int(sandbox["failed"]) for sandbox in sandboxes)
    breakdown = [
        {
            "sandbox_idx": sandbox["sandbox_idx"],
            "sandbox_id": sandbox["sandbox_id"],
            "passed": sandbox["passed"],
            "failed": sandbox["failed"],
            "wall_seconds": sandbox["wall_seconds"],
        }
        for sandbox in sandboxes
    ]
    return {
        "phase": phase_id,
        "parallel": parallel,
        "timeout": timeout,
        "template": template,
        "wall_seconds": round(wall_seconds, 3),
        "passed": passed,
        "failed": failed,
        "sandboxes": json_ready(breakdown),
    }


def _truncate(text: str) -> str:
    return text[:MAX_OUTPUT_CHARS]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(redacted_json_ready(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, content: Any) -> None:
    path.write_text(redact(str(content)), encoding="utf-8")
