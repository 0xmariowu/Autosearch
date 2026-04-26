"""Parallel multi-channel subtask delegation for v2 tool-supplier."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from autosearch.core.channel_runtime import ChannelRuntime

_DEFAULT_CONCURRENCY_CAP = 5
_DEFAULT_PER_CHANNEL_TIMEOUT_SECONDS = 30.0


def _resolve_concurrency_cap() -> int:
    raw = os.environ.get("AUTOSEARCH_DELEGATE_CONCURRENCY", str(_DEFAULT_CONCURRENCY_CAP))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_CONCURRENCY_CAP


def _resolve_per_channel_timeout(per_channel_timeout: float | None) -> float | None:
    if per_channel_timeout is not None:
        return per_channel_timeout if per_channel_timeout > 0 else None

    raw = os.environ.get(
        "AUTOSEARCH_PER_CHANNEL_TIMEOUT_SECONDS",
        str(_DEFAULT_PER_CHANNEL_TIMEOUT_SECONDS),
    )
    try:
        timeout = float(raw)
    except ValueError:
        timeout = _DEFAULT_PER_CHANNEL_TIMEOUT_SECONDS
    return timeout if timeout > 0 else None


@dataclass
class SubtaskResult:
    evidence_by_channel: dict[str, list[dict]] = field(default_factory=dict)
    summary: str = ""
    failed_channels: list[str] = field(default_factory=list)
    failed_channel_details: list[dict] = field(default_factory=list)
    budget_used: dict[str, int] = field(default_factory=dict)


async def run_subtask(
    task_description: str,  # noqa: ARG001 — surfaced to callers for tracing
    channels: list[str],
    query: str,
    max_per_channel: int = 5,
    *,
    channel_runtime: ChannelRuntime,
    per_channel_timeout: float | None = None,
    _search_fn=None,  # injectable for tests
) -> SubtaskResult:
    """Run query across channels concurrently and return a SubtaskResult.

    All channel calls go through the shared ``channel_runtime`` so the
    rate limiter, health tracker, and cost tracker accumulate across
    delegate runs (P0-4). The channel list is order-preserving deduped
    so the same name passed twice is only run once. A semaphore caps
    in-flight calls (default 5; override via
    ``AUTOSEARCH_DELEGATE_CONCURRENCY``) to protect paid APIs from burst.
    """
    from autosearch.core.models import SubQuery  # noqa: PLC0415

    channels = list(dict.fromkeys(channels))
    semaphore = asyncio.Semaphore(_resolve_concurrency_cap())
    resolved_per_channel_timeout = _resolve_per_channel_timeout(per_channel_timeout)

    if _search_fn is None:
        all_channels = {c.name: c for c in channel_runtime.channels}

        async def _search_fn(channel_name: str) -> list[dict]:
            ch = all_channels.get(channel_name)
            if ch is None:
                raise ValueError(f"unknown channel: {channel_name}")
            sq = SubQuery(text=query, rationale=query)
            results = await ch.search(sq)
            return [e.to_slim_dict() for e in results][:max_per_channel]

    result = SubtaskResult()

    async def _run_one(name: str) -> tuple[str, list[dict] | Exception]:
        async with semaphore:
            try:
                if resolved_per_channel_timeout is None:
                    evidence = await _search_fn(name)
                else:
                    evidence = await asyncio.wait_for(
                        _search_fn(name),
                        timeout=resolved_per_channel_timeout,
                    )
                return name, evidence[:max_per_channel]
            except asyncio.TimeoutError:
                return name, asyncio.TimeoutError(
                    f"channel {name} exceeded per-channel timeout of "
                    f"{resolved_per_channel_timeout}s"
                )
            except Exception as exc:  # noqa: BLE001
                return name, exc

    outcomes = await asyncio.gather(*(_run_one(ch) for ch in channels))

    for name, outcome in outcomes:
        if isinstance(outcome, Exception):
            from autosearch.core.channel_status import (  # noqa: PLC0415
                ChannelFailureStatus,
                exception_to_channel_status,
            )

            if isinstance(outcome, asyncio.TimeoutError):
                failure = ChannelFailureStatus(
                    status="transient_error",
                    reason=f"timeout after {resolved_per_channel_timeout}s",
                    fix_hint=(
                        "channel did not respond within deadline; check provider availability "
                        "or increase AUTOSEARCH_PER_CHANNEL_TIMEOUT_SECONDS"
                    ),
                    unmet_requires=[],
                )
            else:
                failure = exception_to_channel_status(outcome)
            result.failed_channels.append(name)
            result.failed_channel_details.append(
                {
                    "channel": name,
                    "status": failure.status,
                    "reason": failure.reason,
                    "fix_hint": failure.fix_hint,
                    "unmet_requires": failure.unmet_requires,
                }
            )
        else:
            result.evidence_by_channel[name] = outcome
            result.budget_used[name] = len(outcome)

    ok = len(result.evidence_by_channel)
    fail = len(result.failed_channels)
    total = sum(result.budget_used.values())
    result.summary = f"{total} results from {ok} channel(s), {fail} failed"

    return result
