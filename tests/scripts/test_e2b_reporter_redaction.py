from __future__ import annotations

from scripts.e2b.lib.reporter import write_task_result


def test_write_task_result_redacts_stdout_and_stderr_before_saving(tmp_path) -> None:
    result = {
        "id": "task",
        "sandbox_idx": 1,
        "sandbox_id": "sandbox",
        "exit_code": 1,
        "stdout": "ANTHROPIC_API_KEY=secret-xyz",
        "stderr": '"ANTHROPIC_API_KEY": "secret-xyz"',
        "wall_seconds": 0.1,
        "passed": False,
        "fail_reason": "Authorization: Bearer abc.def.ghi+/=tail",
    }

    write_task_result(tmp_path, result)

    for path in tmp_path.iterdir():
        content = path.read_text(encoding="utf-8")
        assert "secret-xyz" not in content
        assert "abc.def.ghi+/=tail" not in content
        assert "[REDACTED]" in content
