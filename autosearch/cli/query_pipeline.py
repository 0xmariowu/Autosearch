"""Thin CLI orchestrator that wires the v2 MCP tools into a single command-line query.

Per public-repo-hygiene-plan v2 §P1-7 Option B': autosearch DOES NOT synthesize.
The CLI runs:
  1. run_clarify   → channel_priority list (top N)
  2. run_channel × N (concurrent) → evidence list
  3. render markdown brief with citations + "paste into Claude/ChatGPT" footer

This is the maintainer-side smoke path: a fresh `pipx install autosearch &&
autosearch query "..."` returns evidence + citations without a runtime AI.
For a synthesized report, the user pastes the output into Claude / ChatGPT /
Cursor.

The orchestration deliberately reuses `_invoke_clarifier` and
`_search_single_channel` from `autosearch.mcp.server` so the CLI and the MCP
tool layer share one code path; if the MCP tools regress, the CLI smoke
path catches it.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from autosearch.core.models import SearchMode


@dataclass
class QueryResult:
    """Structured result from `run_query`. Always-set fields kept first."""

    query: str
    channels_used: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    clarify_question: str | None = None
    clarify_options: list[str] = field(default_factory=list)


async def run_query(
    query: str,
    *,
    mode_hint: SearchMode | None = None,
    top_k_channels: int = 3,
    per_channel_k: int = 5,
) -> QueryResult:
    """Run the thin orchestration pipeline and return structured result.

    No LLM synthesis happens here — the runtime AI / human reads the
    returned evidence and decides what to do with it.

    Returns a QueryResult with:
      - clarify_question populated if the clarifier needs disambiguation
        (in which case channels_used / evidence stay empty); or
      - channels_used + evidence populated when the search ran.
    """
    # Imports deferred to avoid circular import via autosearch.cli.main
    from autosearch.core.channel_runtime import get_channel_runtime
    from autosearch.mcp.server import _invoke_clarifier, _search_single_channel

    clarify = await _invoke_clarifier(query, mode_hint)

    if clarify.need_clarification and clarify.question:
        return QueryResult(
            query=query,
            clarify_question=clarify.question,
            clarify_options=list(clarify.question_options),
        )

    channels = list(clarify.channel_priority)[:top_k_channels]
    if not channels:
        # Clarifier returned no priority (rare). Use a sensible English-leaning default
        # that exercises three independent free channels.
        channels = ["arxiv", "ddgs", "github"][:top_k_channels]

    runtime = get_channel_runtime()
    name_to_channel = {c.name: c for c in runtime.channels}

    async def _safe_run(name: str) -> list[Any]:
        ch = name_to_channel.get(name)
        if ch is None:
            return []
        try:
            return await _search_single_channel(ch, query, rationale=query)
        except Exception:  # noqa: BLE001 — channel boundary; one failure shouldn't kill the run
            return []

    results = await asyncio.gather(*(_safe_run(name) for name in channels))

    evidence: list[dict[str, Any]] = []
    for ch_evidence in results:
        for ev in ch_evidence[:per_channel_k]:
            evidence.append(ev.to_slim_dict())

    return QueryResult(
        query=query,
        channels_used=channels,
        evidence=evidence,
    )


def render_markdown(result: QueryResult) -> str:
    """Render the result as a markdown evidence brief with citations."""
    if result.clarify_question:
        lines = [
            "# Clarification needed",
            "",
            f"**Query**: {result.query}",
            "",
            f"**Question**: {result.clarify_question}",
        ]
        if result.clarify_options:
            lines.append("")
            lines.append("**Options**:")
            for option in result.clarify_options:
                lines.append(f"- {option}")
        lines.extend(
            [
                "",
                "Re-run with the clarified query, e.g.:",
                "",
                "```",
                'autosearch query "<your refined question>"',
                "```",
            ]
        )
        return "\n".join(lines)

    if not result.evidence:
        return "\n".join(
            [
                "# No evidence found",
                "",
                f"**Query**: {result.query}",
                f"**Channels tried**: {', '.join(result.channels_used) or '(none)'}",
                "",
                "Try broadening the query or run `autosearch doctor` to check channel availability.",
            ]
        )

    lines = [
        "# AutoSearch evidence brief",
        "",
        f"**Query**: {result.query}",
        f"**Channels**: {', '.join(result.channels_used)}",
        f"**Evidence count**: {len(result.evidence)}",
        "",
        "## Evidence",
        "",
    ]

    for i, ev in enumerate(result.evidence, start=1):
        title = ev.get("title") or "(no title)"
        url = ev.get("url") or ""
        snippet = ev.get("snippet") or ev.get("content") or ""
        source = ev.get("source_channel") or ""
        published = ev.get("published_at") or ""

        lines.append(f"### [{i}] {title}")
        if url:
            lines.append(f"- URL: <{url}>")
        if source:
            lines.append(f"- Source: {source}")
        if published:
            lines.append(f"- Published: {published}")
        if snippet:
            short = snippet[:300].rstrip()
            lines.append(f"- Snippet: {short}{'…' if len(snippet) > 300 else ''}")
        lines.append("")

    lines.append("## Citations")
    lines.append("")
    for i, ev in enumerate(result.evidence, start=1):
        url = ev.get("url") or ""
        title = ev.get("title") or "(no title)"
        lines.append(f"[{i}] {title} — <{url}>")

    lines.extend(
        [
            "",
            "---",
            "",
            "**Note**: AutoSearch does not synthesize a report from this evidence.",
            "Paste the brief above into Claude / ChatGPT / Cursor to get a synthesized answer with citations.",
        ]
    )

    return "\n".join(lines)


def render_json(result: QueryResult) -> str:
    """Render the result as JSON for programmatic consumption."""
    return json.dumps(
        {
            "query": result.query,
            "channels_used": result.channels_used,
            "evidence_count": len(result.evidence),
            "clarify_question": result.clarify_question,
            "clarify_options": result.clarify_options,
            "evidence": result.evidence,
        },
        indent=2,
        default=str,
        ensure_ascii=False,
    )
