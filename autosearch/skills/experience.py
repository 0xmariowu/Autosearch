from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SKILLS_ROOT = Path(__file__).resolve().parent
_SKILL_GROUPS = ("channels", "tools", "meta")


def _find_skill_dir(skill_name: str) -> Path | None:
    """Locate the bundled (read-only) skill directory shipped inside the package."""
    for group in _SKILL_GROUPS:
        skill_dir = _SKILLS_ROOT / group / skill_name
        if skill_dir.is_dir():
            return skill_dir
    return None


def _runtime_root() -> Path:
    """Return the per-user, writable experience root.

    Resolution order:
      1. `$AUTOSEARCH_EXPERIENCE_DIR` (test/CI override)
      2. `$XDG_DATA_HOME/autosearch/experience` (XDG users opt in explicitly)
      3. `~/.autosearch/experience` (matches existing `~/.autosearch/cookies` namespace)
    """
    override = os.environ.get("AUTOSEARCH_EXPERIENCE_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg).expanduser() / "autosearch" / "experience"
    return Path.home() / ".autosearch" / "experience"


def _runtime_skill_dir(skill_name: str) -> Path | None:
    """Return the writable runtime directory for a skill, or None if unknown."""
    bundled = _find_skill_dir(skill_name)
    if bundled is None:
        return None
    group = bundled.parent.name  # channels / tools / meta
    return _runtime_root() / group / skill_name


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
    """Append one event to a skill's raw experience log under the user's data dir.

    String fields in `event` (e.g. `query`) are redacted for secret-shaped
    tokens before write. Capture failures must never break the caller's
    channel call (best-effort).
    """
    try:
        from autosearch.core.redact import redact

        runtime_dir = _runtime_skill_dir(skill_name)
        if runtime_dir is None:
            return
        experience_dir = runtime_dir / "experience"
        experience_dir.mkdir(parents=True, exist_ok=True)
        scrubbed = {k: (redact(v) if isinstance(v, str) else v) for k, v in event.items()}
        patterns_path = experience_dir / "patterns.jsonl"
        with patterns_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(scrubbed, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return


def load_experience_digest(skill_name: str) -> str | None:
    """Return the compact experience digest. Runtime-compacted version wins;
    falls back to the bundled read-only seed shipped with the package."""
    runtime_dir = _runtime_skill_dir(skill_name)
    candidates = []
    if runtime_dir is not None:
        candidates.append(runtime_dir / "experience.md")
    bundled = _find_skill_dir(skill_name)
    if bundled is not None:
        candidates.append(bundled / "experience.md")
    for digest_path in candidates:
        try:
            if digest_path.is_file():
                return digest_path.read_text(encoding="utf-8")
        except OSError:
            continue
    return None


def should_compact(
    skill_name: str,
    new_event_count_threshold: int = 10,
    size_threshold_bytes: int = 65536,
) -> bool:
    """Return whether a skill's raw experience log should be compacted."""
    runtime_dir = _runtime_skill_dir(skill_name)
    if runtime_dir is None:
        return False

    patterns_path = runtime_dir / "experience" / "patterns.jsonl"
    try:
        if not patterns_path.is_file():
            return False
        if patterns_path.stat().st_size >= size_threshold_bytes:
            return True

        compacted_at = _last_compacted_at(runtime_dir / "experience.md")
        if compacted_at is None:
            bundled = _find_skill_dir(skill_name)
            if bundled is not None:
                compacted_at = _last_compacted_at(bundled / "experience.md")
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
