"""Persist learnings across sessions via patterns.jsonl."""

name = "learnings_persist"
description = "Save learnings to patterns.jsonl for cross-session memory. Also load historical learnings from past sessions. This is what makes AutoSearch smarter over time."
when = "At the end of a search session to save learnings. At the start to load historical context."
input_type = "learnings"
output_type = "learnings"
input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "description": "List of learning strings to save, or null to load",
        },
        "context": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["save", "load"],
                    "default": "load",
                },
                "task_spec": {
                    "type": "string",
                    "description": "Task description for tagging saved learnings",
                },
                "max_load": {
                    "type": "integer",
                    "description": "Max historical learnings to load",
                    "default": 20,
                },
            },
        },
    },
}

import json
import time
from pathlib import Path

_PATTERNS_PATH = Path(__file__).parent.parent / "patterns.jsonl"


def run(learnings, **context):
    action = context.get("action", "load")

    if action == "save":
        return _save_learnings(learnings or [], context.get("task_spec", ""))
    else:
        return _load_learnings(context.get("max_load", 20))


def _save_learnings(learnings, task_spec):
    if not learnings:
        return {"saved": 0}

    entries = []
    for learning in learnings:
        if not isinstance(learning, str) or not learning.strip():
            continue
        entry = {
            "type": "orchestrator_learning",
            "text": learning.strip(),
            "task": task_spec,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        entries.append(entry)

    if entries:
        import fcntl

        with open(_PATTERNS_PATH, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            fcntl.flock(f, fcntl.LOCK_UN)

    return {"saved": len(entries), "file": str(_PATTERNS_PATH)}


def _load_learnings(max_load):
    if not _PATTERNS_PATH.exists():
        return []

    learnings = []
    try:
        with open(_PATTERNS_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "orchestrator_learning":
                        learnings.append(entry.get("text", ""))
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []

    # Return most recent learnings
    return learnings[-max_load:] if learnings else []


def test():
    # Test save/load cycle with temp file
    import tempfile

    global _PATTERNS_PATH
    original = _PATTERNS_PATH
    _PATTERNS_PATH = Path(tempfile.mktemp(suffix=".jsonl"))
    try:
        # Save
        result = run(["learning 1", "learning 2"], action="save", task_spec="test")
        assert result["saved"] == 2

        # Load
        loaded = run(None, action="load")
        assert len(loaded) == 2
        assert "learning 1" in loaded

        return "ok"
    finally:
        _PATTERNS_PATH = original
