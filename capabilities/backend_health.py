"""Track backend health with auto-suspension and recovery."""

name = "backend_health"
description = "Track error rates per search backend. Auto-suspend backends after repeated failures (3 consecutive errors). Auto-recover after cooldown period. Prevents wasting API calls on broken backends."
when = "Before searching, to filter out suspended backends. After search errors, to record failures."
input_type = "config"
output_type = "report"

import json
import time
from pathlib import Path

_STATE_PATH = Path(__file__).parent.parent / "sources" / "health-state.json"

# Suspension durations in seconds (copied from SearXNG)
_SUSPENSION_DURATIONS = {
    "timeout": 300,  # 5 minutes
    "rate_limit": 3600,  # 1 hour
    "auth_error": 86400,  # 24 hours
    "unknown_error": 600,  # 10 minutes
}
_MAX_CONSECUTIVE_ERRORS = 3


def _load_state():
    if _STATE_PATH.exists():
        try:
            return json.loads(_STATE_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_state(state):
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(state, indent=2))


def run(input_data, **context):
    action = context.get(
        "action", "check"
    )  # check | record_error | record_success | reset
    backend = context.get("backend", "")
    error_type = context.get("error_type", "unknown_error")

    state = _load_state()
    now = time.time()

    if action == "record_error" and backend:
        entry = state.get(backend, {"errors": 0, "suspended_until": 0})
        entry["errors"] = entry.get("errors", 0) + 1
        entry["last_error"] = now
        entry["last_error_type"] = error_type
        if entry["errors"] >= _MAX_CONSECUTIVE_ERRORS:
            duration = _SUSPENSION_DURATIONS.get(error_type, 600)
            entry["suspended_until"] = now + duration
        state[backend] = entry
        _save_state(state)

    elif action == "record_success" and backend:
        if backend in state:
            state[backend]["errors"] = 0
            state[backend]["suspended_until"] = 0
            _save_state(state)

    elif action == "reset" and backend:
        state.pop(backend, None)
        _save_state(state)

    # Build report
    report = {}
    for name_key, entry in state.items():
        suspended_until = entry.get("suspended_until", 0)
        is_suspended = suspended_until > now
        report[name_key] = {
            "errors": entry.get("errors", 0),
            "suspended": is_suspended,
            "suspended_until": suspended_until if is_suspended else 0,
            "recovery_in_seconds": max(0, int(suspended_until - now))
            if is_suspended
            else 0,
        }

    return report


def test():
    import tempfile

    global _STATE_PATH
    original = _STATE_PATH
    _STATE_PATH = Path(tempfile.mktemp(suffix=".json"))
    try:
        # Record 3 errors -> should suspend
        for _ in range(3):
            run(
                None,
                action="record_error",
                backend="test_backend",
                error_type="timeout",
            )
        report = run(None, action="check")
        assert report["test_backend"]["suspended"], "Should be suspended after 3 errors"
        assert report["test_backend"]["errors"] == 3

        # Record success -> should clear
        run(None, action="record_success", backend="test_backend")
        report = run(None, action="check")
        assert not report["test_backend"]["suspended"], (
            "Should not be suspended after success"
        )

        return "ok"
    finally:
        _STATE_PATH = original
