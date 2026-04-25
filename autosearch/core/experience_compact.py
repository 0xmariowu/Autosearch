from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autosearch.core.experience_privacy import query_shape_label, shape_from_legacy_query
from autosearch.skills.experience import _parse_datetime, _runtime_skill_dir


@dataclass
class _PatternStats:
    seen: int = 0
    success: int = 0
    last_verified: datetime | None = None


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    return cleaned[:300]


def _update_last_verified(current: datetime | None, payload: dict[str, Any]) -> datetime | None:
    event_ts = _parse_datetime(payload.get("ts"))
    if event_ts is None:
        return current
    if current is None or event_ts > current:
        return event_ts
    return current


def _date_text(value: datetime | None) -> str:
    if value is None:
        return "unknown"
    return value.date().isoformat()


def _sort_datetime(value: datetime | None) -> datetime:
    return value or datetime.min.replace(tzinfo=UTC)


def _read_events(patterns_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with patterns_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                channel = str(payload.get("channel") or payload.get("skill") or "unknown")
                outcome = str(payload.get("outcome") or "unknown")
                if "query_shape" not in payload and "query" in payload:
                    legacy_shape = shape_from_legacy_query(
                        payload.get("query"),
                        channel=channel,
                        outcome=outcome,
                    )
                    if legacy_shape is not None:
                        payload["query_shape"] = legacy_shape
                payload.pop("query", None)
                events.append(payload)
    return events


def compact(skill_name: str) -> bool:
    """Promote recurring raw experience events into a compact skill digest."""
    try:
        runtime_dir = _runtime_skill_dir(skill_name)
        if runtime_dir is None:
            return False

        patterns_path = runtime_dir / "experience" / "patterns.jsonl"
        if not patterns_path.is_file():
            return False

        events = _read_events(patterns_path)
        winning_patterns: dict[str, _PatternStats] = {}
        failure_modes: Counter[str] = Counter()
        failure_last_seen: dict[str, datetime | None] = {}
        good_queries: Counter[str] = Counter()
        good_query_last_seen: dict[str, datetime | None] = {}

        for event in events:
            outcome = event.get("outcome")
            winning_pattern = _clean_text(event.get("winning_pattern"))
            if winning_pattern is not None:
                stats = winning_patterns.setdefault(winning_pattern, _PatternStats())
                stats.seen += 1
                if outcome == "success":
                    stats.success += 1
                stats.last_verified = _update_last_verified(stats.last_verified, event)

            failure_mode = _clean_text(event.get("failure_mode"))
            if failure_mode is not None:
                failure_modes[failure_mode] += 1
                failure_last_seen[failure_mode] = _update_last_verified(
                    failure_last_seen.get(failure_mode),
                    event,
                )

            good_query = _clean_text(event.get("good_query"))
            if good_query is None:
                good_query = query_shape_label(event.get("query_shape"))
            if good_query is not None:
                good_queries[good_query] += 1
                good_query_last_seen[good_query] = _update_last_verified(
                    good_query_last_seen.get(good_query),
                    event,
                )

        active_rules = [
            (pattern, stats)
            for pattern, stats in winning_patterns.items()
            if stats.seen >= 3 and stats.success >= 2
        ]
        active_rules.sort(
            key=lambda item: (
                item[1].success,
                item[1].seen,
                _sort_datetime(item[1].last_verified),
                item[0],
            ),
            reverse=True,
        )

        ordered_failures = sorted(
            failure_modes.items(),
            key=lambda item: (
                item[1],
                _sort_datetime(failure_last_seen.get(item[0])),
                item[0],
            ),
            reverse=True,
        )
        ordered_good_queries = sorted(
            good_queries.items(),
            key=lambda item: (
                item[1],
                _sort_datetime(good_query_last_seen.get(item[0])),
                item[0],
            ),
            reverse=True,
        )

        compacted_at = datetime.now(UTC).isoformat()
        lines = [
            f"# {skill_name} experience",
            "",
            "## Active Rules",
        ]
        if active_rules:
            for pattern, stats in active_rules[:20]:
                lines.append(
                    "- "
                    f"{pattern} -- seen={stats.seen}, success={stats.success}, "
                    f"last_verified={_date_text(stats.last_verified)}"
                )
        else:
            lines.append("- None yet.")

        lines.extend(["", "## Failure Modes"])
        if ordered_failures:
            for failure_mode, seen in ordered_failures[:15]:
                lines.append(
                    "- "
                    f"{failure_mode} -- seen={seen}, "
                    f"last_verified={_date_text(failure_last_seen.get(failure_mode))}"
                )
        else:
            lines.append("- None yet.")

        lines.extend(["", "## Good Query Patterns"])
        if ordered_good_queries:
            for good_query, seen in ordered_good_queries[:20]:
                lines.append(
                    "- "
                    f"`{good_query}` -- seen={seen}, "
                    f"last_verified={_date_text(good_query_last_seen.get(good_query))}"
                )
        else:
            lines.append("- None yet.")

        lines.extend(
            [
                "",
                "## Last Compacted",
                f"Last Compacted: {compacted_at}",
                f"- from {len(events)} events, promoted {min(len(active_rules), 20)} rules.",
                "",
            ]
        )

        digest_path = runtime_dir / "experience.md"
        digest_path.write_text("\n".join(lines[:120]), encoding="utf-8")
        return True
    except Exception:
        return False
