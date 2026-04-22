"""Recent-signal-fusion: filter and sort evidence by recency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def filter_recent(
    evidence_list: list[dict],
    days: int = 30,
    *,
    date_keys: tuple[str, ...] = ("date", "published_at", "created_at", "ts", "timestamp"),
) -> list[dict]:
    """Return evidence items published within the last `days` days, newest first.

    Tries each key in date_keys to find a parseable date. Items with no
    parseable date are excluded from results.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    dated: list[tuple[datetime, dict]] = []

    for item in evidence_list:
        dt = _parse_date(item, date_keys)
        if dt is not None and dt >= cutoff:
            dated.append((dt, item))

    dated.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in dated]


def _parse_date(item: dict, date_keys: tuple[str, ...]) -> datetime | None:
    for key in date_keys:
        raw = item.get(key)
        if not raw:
            continue
        dt = _try_parse(str(raw))
        if dt is not None:
            return dt
    return None


def _try_parse(raw: str) -> datetime | None:
    from datetime import timezone

    raw = raw.strip()
    if not raw:
        return None

    # ISO 8601 with Z suffix
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # Unix timestamp (int or float string)
    try:
        ts = float(raw)
        return datetime.fromtimestamp(ts, tz=UTC)
    except (ValueError, OSError):
        pass

    return None
