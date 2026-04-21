import json
import shutil
import subprocess


def claude_code_unavailable_reason() -> str | None:
    if shutil.which("claude") is None:
        return "claude binary not found on PATH"

    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError as exc:
        return f"claude auth status unavailable: {exc}"

    payload = result.stdout.strip() or result.stderr.strip()
    if payload:
        try:
            auth_status = json.loads(payload)
        except json.JSONDecodeError:
            auth_status = None
        if isinstance(auth_status, dict) and auth_status.get("loggedIn") is False:
            return "claude auth status reports loggedIn=false"
        if not (isinstance(auth_status, dict) and auth_status.get("loggedIn") is True):
            return "claude auth status unavailable"
    else:
        return "claude auth status unavailable"

    try:
        probe = subprocess.run(
            ["claude", "-p", "Reply with OK only.", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError as exc:
        return f"claude prompt probe unavailable: {exc}"
    except subprocess.TimeoutExpired:
        return "claude prompt probe timed out"

    probe_payload = probe.stdout.strip() or probe.stderr.strip()
    if probe.returncode != 0:
        reason = _probe_failure_reason(probe_payload)
        return f"claude prompt probe failed: {reason}" if reason else "claude prompt probe failed"

    if not probe_payload:
        return "claude prompt probe returned empty output"

    try:
        probe_result = json.loads(probe_payload)
    except json.JSONDecodeError:
        return "claude prompt probe returned invalid JSON"

    if isinstance(probe_result, dict) and probe_result.get("is_error") is True:
        reason = _probe_failure_reason(probe_payload)
        return f"claude prompt probe failed: {reason}" if reason else "claude prompt probe failed"

    return None


def _probe_failure_reason(payload: str) -> str | None:
    if not payload:
        return None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload

    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, str) and result.strip():
            return result.strip()
        message = data.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    return payload
