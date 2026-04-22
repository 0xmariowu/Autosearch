"""Trace-harvest: extract winning query patterns from run_channel traces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Pattern:
    query: str
    channel: str
    score: float  # 0.0–1.0 based on count_returned / count_total


def extract_winning_patterns(
    trace: dict,
    *,
    min_score: float = 0.5,
) -> list[Pattern]:
    """Extract high-scoring query patterns from a run_channel trace dict.

    trace format (subset of RunChannelResponse fields):
      {channel, query, count_returned, count_total, outcome}

    Returns patterns with score >= min_score.
    """
    channel = str(trace.get("channel") or "")
    query = str(trace.get("query") or "")
    outcome = str(trace.get("outcome") or "")
    count_returned = int(trace.get("count_returned") or 0)
    count_total = int(trace.get("count_total") or 0)

    if not channel or not query or outcome == "error":
        return []

    score = (count_returned / count_total) if count_total > 0 else 0.0
    if score < min_score:
        return []

    return [Pattern(query=query, channel=channel, score=score)]


def harvest_to_patterns_jsonl(
    traces: list[dict],
    channel_name: str,
    *,
    min_score: float = 0.5,
    patterns_file: Path | None = None,
) -> list[Pattern]:
    """Extract winning patterns from a list of traces and append to patterns.jsonl.

    Returns the list of patterns that passed the score threshold.
    """
    import json
    from datetime import UTC, datetime

    winners: list[Pattern] = []
    for trace in traces:
        winners.extend(extract_winning_patterns(trace, min_score=min_score))

    if winners and patterns_file is not None:
        patterns_file.parent.mkdir(parents=True, exist_ok=True)
        with patterns_file.open("a", encoding="utf-8") as fh:
            for pattern in winners:
                fh.write(
                    json.dumps(
                        {
                            "query": pattern.query,
                            "channel": pattern.channel,
                            "score": pattern.score,
                            "ts": datetime.now(UTC).isoformat(),
                        }
                    )
                    + "\n"
                )

    return winners
