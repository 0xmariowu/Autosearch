from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import pytest

from autosearch.channels.base import ChannelRegistry
from autosearch.core.environment_probe import probe_environment
from autosearch.core.models import SubQuery
from autosearch.init.channel_status import default_channels_root

BASELINE_FILE = Path(__file__).resolve().parent / "channel_wall_time_baseline.json"
REPORT_FILE = Path(__file__).resolve().parent / "channel_wall_time_last.json"

# Channels with free, stable, no-key upstreams that are cheap to probe.
STABLE_T0_CHANNELS = (
    "arxiv",
    "devto",
    "hackernews",
    "stackoverflow",
    "wikipedia",
    "wikidata",
)

PROBE_QUERY = SubQuery(
    text="retrieval augmented generation",
    rationale="perf baseline probe",
)

PER_CHANNEL_TIMEOUT_S = 20.0
REGRESSION_FACTOR = 3.0


async def _time_channel(channel) -> tuple[float, int, str | None]:
    start = time.perf_counter()
    try:
        async with asyncio.timeout(PER_CHANNEL_TIMEOUT_S):
            evidences = await channel.search(PROBE_QUERY)
    except (TimeoutError, Exception) as exc:  # noqa: BLE001 — record all failures
        elapsed = time.perf_counter() - start
        return elapsed, 0, f"{type(exc).__name__}: {exc}"
    return time.perf_counter() - start, len(evidences), None


def _load_baseline() -> dict[str, float]:
    if not BASELINE_FILE.exists():
        return {}
    try:
        return json.loads(BASELINE_FILE.read_text())
    except (OSError, ValueError):
        return {}


@pytest.mark.perf
@pytest.mark.network
@pytest.mark.asyncio
async def test_channel_wall_time_baseline() -> None:
    """Measure wall-time for stable T0 channels and compare against baseline.

    Writes the current run to `channel_wall_time_last.json`. If a baseline file
    exists, flags regressions > REGRESSION_FACTOR × baseline. Does NOT fail on
    first run (no baseline) or on upstream flakiness (recorded as None).

    Run on-demand: `pytest -m perf -q tests/perf/test_channel_wall_time.py -s`
    """
    env = probe_environment()
    registry = ChannelRegistry.compile_from_skills(
        default_channels_root(), env, log_missing_impls=False
    )

    results: dict[str, dict[str, object]] = {}
    for name in STABLE_T0_CHANNELS:
        channel = next(
            (c for c in registry.all_channels() if c.name == name),
            None,
        )
        if channel is None:
            results[name] = {"elapsed_s": None, "evidences": 0, "error": "not_registered"}
            continue

        elapsed, evidence_count, error = await _time_channel(channel)
        results[name] = {
            "elapsed_s": round(elapsed, 3),
            "evidences": evidence_count,
            "error": error,
        }

    REPORT_FILE.write_text(json.dumps(results, indent=2, sort_keys=True))

    baseline = _load_baseline()
    regressions: list[str] = []
    for name, row in results.items():
        elapsed = row["elapsed_s"]
        if elapsed is None or row["error"] is not None:
            continue
        baseline_elapsed = baseline.get(name)
        if baseline_elapsed is None:
            continue
        if elapsed > baseline_elapsed * REGRESSION_FACTOR:
            regressions.append(
                f"{name}: {elapsed:.2f}s vs baseline {baseline_elapsed:.2f}s "
                f"(>{REGRESSION_FACTOR}×)"
            )

    if os.getenv("AUTOSEARCH_PERF_WRITE_BASELINE") == "1":
        flat_baseline = {
            name: row["elapsed_s"]
            for name, row in results.items()
            if isinstance(row["elapsed_s"], (int, float)) and row["error"] is None
        }
        BASELINE_FILE.write_text(json.dumps(flat_baseline, indent=2, sort_keys=True))
        pytest.skip(f"Wrote new baseline to {BASELINE_FILE.name}")

    assert not regressions, "Channel wall-time regressions:\n  " + "\n  ".join(regressions)
