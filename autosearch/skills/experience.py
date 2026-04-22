from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SKILLS_ROOT = Path(__file__).resolve().parent
_SKILL_GROUPS = ("channels", "tools", "meta")


def _find_skill_dir(skill_name: str) -> Path | None:
    for group in _SKILL_GROUPS:
        skill_dir = _SKILLS_ROOT / group / skill_name
        if skill_dir.is_dir():
            return skill_dir
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _last_compacted_at(experience_md: Path) -> datetime | None:
    try:
        lines = experience_md.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Last Compacted:"):
            return _parse_datetime(stripped.partition(":")[2].strip())
        if stripped == "## Last Compacted":
            for next_line in lines[index + 1 :]:
                candidate = next_line.strip().lstrip("-").strip().split(",", maxsplit=1)[0]
                parsed = _parse_datetime(candidate)
                if parsed is not None:
                    return parsed
                if next_line.strip().startswith("## "):
                    break
    return None


def append_event(skill_name: str, event: dict) -> None:
    """Append one event to a skill's raw experience log.

    This helper is intentionally best-effort. Experience capture should never
    break the caller's primary channel execution path.
    """
    try:
        skill_dir = _find_skill_dir(skill_name)
        if skill_dir is None:
            return
        experience_dir = skill_dir / "experience"
        experience_dir.mkdir(parents=True, exist_ok=True)
        patterns_path = experience_dir / "patterns.jsonl"
        with patterns_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return


def load_experience_digest(skill_name: str) -> str | None:
    """Return the compact experience digest for a skill, if present."""
    skill_dir = _find_skill_dir(skill_name)
    if skill_dir is None:
        return None
    try:
        digest_path = skill_dir / "experience.md"
        if not digest_path.is_file():
            return None
        return digest_path.read_text(encoding="utf-8")
    except OSError:
        return None


def should_compact(
    skill_name: str,
    new_event_count_threshold: int = 10,
    size_threshold_bytes: int = 65536,
) -> bool:
    """Return whether a skill's raw experience log should be compacted."""
    skill_dir = _find_skill_dir(skill_name)
    if skill_dir is None:
        return False

    patterns_path = skill_dir / "experience" / "patterns.jsonl"
    try:
        if not patterns_path.is_file():
            return False
        if patterns_path.stat().st_size >= size_threshold_bytes:
            return True

        compacted_at = _last_compacted_at(skill_dir / "experience.md")
        new_events = 0
        with patterns_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event_ts: datetime | None = None
                if compacted_at is not None:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        payload = {}
                    if isinstance(payload, dict):
                        event_ts = _parse_datetime(payload.get("ts"))
                if compacted_at is None or event_ts is None or event_ts > compacted_at:
                    new_events += 1
                    if new_events >= new_event_count_threshold:
                        return True
    except OSError:
        return False

    return False
