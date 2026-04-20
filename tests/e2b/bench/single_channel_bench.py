"""Single-channel bench driver for F111 / F204.

Runs autosearch Pipeline with only ONE target channel enabled and emits JSON
metrics to stdout. Used by E2B matrix to produce per-channel health cards
without requiring autosearch CLI to add a --only-channel flag.

Usage:
    python single_channel_bench.py <channel_name> "<query>"

Output (stdout, single JSON line):
    {
      "channel": ...,
      "query": ...,
      "wall_time": ...,
      "evidence_count": ...,
      "avg_content_len": ...,
      "unique_urls": ...,
      "markdown_len": ...,
      "iterations": ...,
      "prompt_tokens": ...,
      "completion_tokens": ...,
      "cost_usd": ...,
      "channel_empty_calls": {...},
      "status": "ok" | "empty_report" | "channel_unavailable"
    }

Exit code:
    0 on successful run (even if evidence count is 0 — zero evidence IS the signal)
    2 on channel_unavailable (no such channel registered)
    1 on any other failure
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time

from autosearch.core.channel_bootstrap import _build_channels
from autosearch.core.models import SearchMode
from autosearch.core.pipeline import Pipeline
from autosearch.llm.client import LLMClient
from autosearch.observability.cost import CostTracker


async def run_bench(channel_name: str, query: str, mode: SearchMode = SearchMode.FAST) -> dict:
    all_channels = _build_channels()
    target = [c for c in all_channels if c.name == channel_name]
    if not target:
        return {
            "channel": channel_name,
            "query": query,
            "status": "channel_unavailable",
            "available_names": sorted(c.name for c in all_channels),
        }

    tracker = CostTracker()
    llm = LLMClient(provider_chain=["anthropic"], cost_tracker=tracker)
    pipeline = Pipeline(llm=llm, channels=target, cost_tracker=tracker)

    t0 = time.monotonic()
    result = await pipeline.run(query, mode_hint=mode)
    wall = time.monotonic() - t0

    evidences = result.evidences or []
    urls = {e.url for e in evidences if getattr(e, "url", None)}
    content_lens = []
    for e in evidences:
        for attr in ("cleaned_html", "content", "snippet"):
            val = getattr(e, attr, None)
            if val:
                content_lens.append(len(val))
                break

    return {
        "channel": channel_name,
        "query": query,
        "wall_time": round(wall, 2),
        "evidence_count": len(evidences),
        "avg_content_len": round(statistics.mean(content_lens), 1) if content_lens else 0,
        "p50_content_len": round(statistics.median(content_lens), 1) if content_lens else 0,
        "unique_urls": len(urls),
        "markdown_len": len(result.markdown or ""),
        "iterations": result.iterations,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "cost_usd": round(result.cost, 4),
        "channel_empty_calls": dict(result.channel_empty_calls),
        "status": "ok" if (result.markdown or "").strip() else "empty_report",
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: single_channel_bench.py <channel> <query>", file=sys.stderr)
        return 1

    channel_name, query = sys.argv[1], sys.argv[2]

    try:
        stats = asyncio.run(run_bench(channel_name, query))
    except Exception as exc:
        import traceback

        tb = traceback.format_exc()
        stats = {
            "channel": channel_name,
            "query": query,
            "status": "exception",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback_tail": tb.split("\n")[-20:] if tb else [],
        }
        print(json.dumps(stats))
        print("---FULL TRACEBACK---", file=sys.stderr)
        print(tb, file=sys.stderr)
        return 1

    print(json.dumps(stats))
    if stats["status"] == "channel_unavailable":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
