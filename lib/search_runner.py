#!/usr/bin/env python3
"""AutoSearch parallel search runner.

Claude calls this once via Bash. It searches all channels in parallel,
normalizes results, deduplicates, and returns clean JSONL to stdout.

Usage:
    python search_runner.py queries.json
    python search_runner.py '[{"channel":"zhihu","query":"AI agent"}]'
    echo '[...]' | python search_runner.py -

Input: JSON array of query objects:
    [{"channel": "zhihu", "query": "自进化 AI agent", "max_results": 10}]

Output: JSONL to stdout (one result per line), errors to stderr.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from channels import load_channels as load_channel_plugins

# --- Error types ---

# Transient: worth retrying once (network blip, temporary overload)
# Non-transient: don't retry (auth missing, rate-limited, parse failure)
TRANSIENT_ERRORS = {"timeout", "network"}
NON_TRANSIENT_ERRORS = {"rate_limit", "auth", "parse", "unknown"}
ALL_ERROR_TYPES = TRANSIENT_ERRORS | NON_TRANSIENT_ERRORS


class SearchError(Exception):
    """Raised by channels and engines on search failure.

    Returning [] means "searched successfully, found nothing."
    Raising SearchError means "search failed, record to circuit breaker."
    """

    def __init__(
        self,
        *,
        channel: str,
        error_type: str = "unknown",
        message: str = "",
        engine: str | None = None,
    ) -> None:
        self.channel = channel
        self.error_type = error_type if error_type in ALL_ERROR_TYPES else "unknown"
        self.engine = engine
        super().__init__(f"[{channel}] {error_type}: {message}")


DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RESULTS = 10
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}
MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}

# --- Channel health / circuit breaker ---

_HEALTH_FILE: Path | None = None
_channel_health: dict[str, dict] = {}


def _find_health_file() -> Path:
    """Find state/channel-health.json relative to the project root."""
    global _HEALTH_FILE
    if _HEALTH_FILE is not None:
        return _HEALTH_FILE
    # Try relative to this file (lib/search_runner.py → project root)
    root = Path(__file__).resolve().parent.parent
    state_dir = root / "state"
    if state_dir.is_dir():
        _HEALTH_FILE = state_dir / "channel-health.json"
        return _HEALTH_FILE
    # Fallback: current directory
    _HEALTH_FILE = Path("state/channel-health.json")
    return _HEALTH_FILE


def _load_health() -> dict[str, dict]:
    """Load channel health state from disk."""
    global _channel_health
    path = _find_health_file()
    if path.exists():
        try:
            _channel_health = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            _channel_health = {}
    return _channel_health


def _save_health() -> None:
    """Persist channel health state to disk."""
    path = _find_health_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_channel_health, indent=2) + "\n")
    except OSError:
        pass


def _is_suspended(channel: str) -> bool:
    """Check if a channel is currently suspended."""
    entry = _channel_health.get(channel)
    if not entry:
        return False
    until = entry.get("suspended_until", "")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


def _record_failure(channel: str, error: str) -> None:
    """Record a channel failure, update suspension."""
    entry = _channel_health.setdefault(channel, {"consecutive_failures": 0})
    entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
    entry["last_error"] = error[:200]
    entry["last_failure"] = datetime.now(timezone.utc).isoformat()
    # Backoff: min(failures * 60, 3600) seconds
    suspend_secs = min(entry["consecutive_failures"] * 60, 3600)
    from datetime import timedelta

    entry["suspended_until"] = (
        datetime.now(timezone.utc) + timedelta(seconds=suspend_secs)
    ).isoformat()


def _record_success(channel: str) -> None:
    """Reset channel failure state on success."""
    if channel in _channel_health:
        _channel_health[channel] = {"consecutive_failures": 0}


# --- URL normalization ---


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        query = ""
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            query = urlencode(
                {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS},
                doseq=True,
            )
        path = parsed.path.rstrip("/") or "/"
        netloc = parsed.netloc.lower()
        if netloc == "github.com" or netloc.endswith(".github.com"):
            path = re.sub(r"/(tree|blob)/(main|master)/?$", "", path)
        return urlunparse(
            (parsed.scheme, parsed.netloc.lower(), path, parsed.params, query, "")
        )
    except Exception:
        return url


# --- Date extraction ---


def extract_date(text: str, url: str = "") -> str | None:
    combined = f"{url} {text}"
    if match := re.search(r"(\d{2})(\d{2})\.\d{4,5}", combined):
        yy, mm = match.groups()
        if 20 <= int(yy) <= 30 and 1 <= int(mm) <= 12:
            return f"20{yy}-{mm}-01T00:00:00Z"
    if match := re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/", url):
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}T00:00:00Z"
    if match := re.search(r"(\d{4})-(\d{2})-(\d{2})", text):
        year, month, day = match.groups()
        return f"{year}-{month}-{day}T00:00:00Z"
    lowered = text.lower()
    for month_name, month_num in MONTH_MAP.items():
        pattern = rf"(?:published|updated|posted|date)?\s*{month_name}\w*\.?\s+\d{{1,2}},?\s+(\d{{4}})"
        if match := re.search(pattern, lowered):
            return f"{match.group(1)}-{month_num}-01T00:00:00Z"
    if match := re.search(r"\((\d{4})\)", text):
        year = int(match.group(1))
        if 2020 <= year <= 2030:
            return f"{year}-01-01T00:00:00Z"
    return None


# --- Result builder ---


def make_result(
    url: str,
    title: str,
    snippet: str,
    source: str,
    query: str,
    extra_metadata: dict | None = None,
) -> dict:
    metadata: dict[str, Any] = {}
    if date := extract_date(f"{snippet} {title}", url):
        metadata["published_at"] = date
    if extra_metadata:
        metadata.update(extra_metadata)
    return {
        "url": normalize_url(url),
        "title": title.strip(),
        "snippet": snippet.strip()[:500],
        "source": source,
        "query": query,
        "metadata": metadata,
    }


# --- Channel execution ---

CHANNEL_METHODS = load_channel_plugins()


async def run_single_query(query_obj: dict) -> list[dict]:
    channel = query_obj.get("channel", "web-ddgs")
    query = query_obj.get("query", "")
    max_results = query_obj.get("max_results", DEFAULT_MAX_RESULTS)
    if not query:
        return []

    # Circuit breaker: skip suspended channels
    if _is_suspended(channel):
        entry = _channel_health.get(channel, {})
        print(
            f"[search_runner] skipped {channel} (suspended until {entry.get('suspended_until', '?')}, "
            f"failures={entry.get('consecutive_failures', 0)}, last={entry.get('last_error', '')})",
            file=sys.stderr,
        )
        return []

    method = CHANNEL_METHODS.get(channel)
    if method is None:
        print(f"[search_runner] unknown channel: {channel}", file=sys.stderr)
        return []
    try:
        results = await asyncio.wait_for(
            method(query, max_results), timeout=DEFAULT_TIMEOUT
        )
        # Any non-exception return (including []) counts as success.
        # A channel returning [] means "searched OK, found nothing" —
        # this should NOT count as a failure in the circuit breaker.
        _record_success(channel)
        return results
    except SearchError as exc:
        _record_failure(channel, f"{exc.error_type}: {exc}")
        print(f"[search_runner] {exc}", file=sys.stderr)
        return []
    except asyncio.TimeoutError:
        _record_failure(channel, "timeout")
        print(f"[search_runner] timeout: {channel} '{query}'", file=sys.stderr)
        return []
    except Exception as exc:
        _record_failure(channel, f"unknown: {exc!s}"[:100])
        print(f"[search_runner] error: {channel} '{query}': {exc}", file=sys.stderr)
        return []


# --- Deduplication ---


def dedup_results(results: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for result in results:
        url = result.get("url", "")
        if not url:
            continue
        key = normalize_url(url)
        if key not in seen or len(json.dumps(result.get("metadata", {}))) > len(
            json.dumps(seen[key].get("metadata", {}))
        ):
            seen[key] = result
    return list(seen.values())


# --- Main ---


async def main(queries: list[dict]) -> None:
    if not queries:
        return

    _load_health()

    results_lists = await asyncio.gather(
        *(run_single_query(query) for query in queries), return_exceptions=True
    )
    all_results: list[dict] = []
    for index, result in enumerate(results_lists):
        if isinstance(result, Exception):
            print(f"[search_runner] query {index} exception: {result}", file=sys.stderr)
            continue
        all_results.extend(result)
    unique_results = dedup_results(all_results)
    for result in unique_results:
        print(json.dumps(result, ensure_ascii=False))

    # Persist health state for next run
    _save_health()

    # Summary to stderr
    suspended = sum(
        1 for ch in set(q.get("channel") for q in queries) if _is_suspended(ch)
    )
    print(
        f"[search_runner] {len(unique_results)} results ({len(all_results)} before dedup) "
        f"from {len(queries)} queries ({suspended} channels suspended)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search_runner.py queries.json", file=sys.stderr)
        print(
            '       python search_runner.py \'[{"channel":"zhihu","query":"AI agent"}]\'',
            file=sys.stderr,
        )
        sys.exit(2)
    arg = sys.argv[1]
    raw = (
        sys.stdin.read()
        if arg == "-"
        else arg
        if arg.startswith("[")
        else Path(arg).read_text()
    )
    try:
        queries = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[search_runner] invalid JSON: {exc}", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(queries))
