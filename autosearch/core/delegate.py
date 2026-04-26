"""Parallel multi-channel subtask delegation for v2 tool-supplier."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from autosearch.core.channel_runtime import ChannelRuntime


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
    _search_fn=None,  # injectable for tests
) -> SubtaskResult:
    """Run query across channels concurrently and return a SubtaskResult."""
    from autosearch.core.models import SubQuery  # noqa: PLC0415

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
        try:
            evidence = await _search_fn(name)
            return name, evidence[:max_per_channel]
        except Exception as exc:  # noqa: BLE001
            return name, exc

    outcomes = await asyncio.gather(*(_run_one(ch) for ch in channels))

    for name, outcome in outcomes:
        if isinstance(outcome, Exception):
            from autosearch.core.channel_status import exception_to_channel_status  # noqa: PLC0415

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
